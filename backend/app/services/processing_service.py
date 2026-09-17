"""The async processing pipeline's actual logic — separate from Celery's task
wrapper (app/workers/tasks.py) so it can be unit-tested with a plain Session,
no broker or worker process required.

Today this pipeline has exactly one real stage: text normalization. Phase 4
inserts AI classification/extraction between NORMALIZE and COMPLETE; Phase 5
inserts rule evaluation and routing after that. Each phase extends this same
function rather than replacing it.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.request import ProcessingStatus, Request
from app.services import audit_service

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Collapse runs of whitespace and trim. Deterministic and pure — the AI
    pipeline (Phase 4) will run classification against this cleaned text
    instead of the raw, possibly messy, user-submitted description."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def run_pipeline(db: Session, request_id: uuid.UUID) -> None:
    request = db.get(Request, request_id)
    if request is None:
        # Not a transient failure — retrying won't make a deleted/nonexistent
        # request appear. Log and stop; there's nothing to write a failure
        # record against.
        logger.warning("processing_pipeline request_not_found request_id=%s", request_id)
        return

    if request.processing_status == ProcessingStatus.COMPLETED:
        # Idempotency guard: Celery's at-least-once delivery means this task can
        # run more than once for the same request (e.g. a worker crashes after
        # finishing but before acknowledging the message). Re-running a
        # completed pipeline would duplicate audit logs and processing_run rows
        # for no benefit, so we skip.
        logger.info("processing_pipeline already_completed request_id=%s", request_id)
        return

    started_at = datetime.now(timezone.utc)
    run = ProcessingRun(
        request_id=request.id,
        stage="NORMALIZE",
        status=ProcessingRunStatus.STARTED,
        started_at=started_at,
    )
    db.add(run)

    request.processing_status = ProcessingStatus.IN_PROGRESS
    db.flush()
    audit_service.record_event(
        db,
        request_id=request.id,
        event_type="PROCESSING_STARTED",
        actor="celery-worker",
        description="Async processing pipeline started",
    )
    db.commit()

    try:
        request.normalized_description = normalize_text(request.description)
        request.processing_status = ProcessingStatus.COMPLETED
        db.flush()

        run.status = ProcessingRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)

        audit_service.record_event(
            db,
            request_id=request.id,
            event_type="TEXT_NORMALIZED",
            actor="celery-worker",
            description="Description normalized",
        )
        audit_service.record_event(
            db,
            request_id=request.id,
            event_type="PROCESSING_COMPLETED",
            actor="celery-worker",
            description="Async processing pipeline completed",
        )
        db.commit()
    except OperationalError:
        # The database itself is unreachable — writing a "this failed" record to
        # that same unreachable database would just fail again. Roll back and let
        # it propagate: Celery's autoretry_for (app/workers/tasks.py) catches this
        # specific exception and retries the whole task later with a fresh
        # connection, rather than us trying to self-diagnose here.
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        request = db.get(Request, request_id)
        run = db.get(ProcessingRun, run.id)

        request.processing_status = ProcessingStatus.FAILED
        run.status = ProcessingRunStatus.FAILED
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.flush()

        audit_service.record_event(
            db,
            request_id=request.id,
            event_type="PROCESSING_FAILED",
            actor="celery-worker",
            description=f"Async processing pipeline failed: {exc}",
        )
        db.commit()
        raise
