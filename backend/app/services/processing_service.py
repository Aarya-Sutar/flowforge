"""The async processing pipeline's actual logic — separate from Celery's task
wrapper (app/workers/tasks.py) so it can be unit-tested with a plain Session,
no broker, worker process, or AI provider network access required.

Pipeline stages: NORMALIZE -> CLASSIFY -> ROUTE. Each phase extended this
same function rather than replacing it — ROUTE (Phase 5) is where the
deterministic rule engine turns AI output into an actual business decision.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.factory import get_ai_provider
from app.models.extracted_entity import ExtractedEntity
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.request import ProcessingStatus, Request, RequestPriority, RequestStatus
from app.models.workflow_task import TaskStatus, WorkflowTask
from app.rules.engine import evaluate_rules
from app.services import audit_service
from app.services.locking import pipeline_lock

# Maps a request's category to the task_type recorded on the WorkflowTask
# created when routing succeeds — purely descriptive labeling, not a routing
# decision (the rule engine, not this dict, decides *whether* and *where*
# to route).
_TASK_TYPE_BY_CATEGORY = {
    "IT_SUPPORT": "IT_TASK",
    "HR": "HR_TASK",
    "FINANCE": "FINANCE_TASK",
    "PROCUREMENT": "PROCUREMENT_TASK",
    "CUSTOMER_SERVICE": "CUSTOMER_SERVICE_TASK",
    "ACCESS_REQUEST": "ACCESS_REVIEW_TASK",
    "GENERAL": "GENERAL_TASK",
}

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")

# Exceptions worth retrying the whole Celery task for — see app/workers/tasks.py.
# A DB hiccup and a one-off bad/unreachable AI response are both plausibly
# transient; a KeyError or a programming bug is not, and falls through to the
# generic failure path instead.
RETRYABLE_EXCEPTIONS = (OperationalError, AIProviderError, AIOutputValidationError)


def normalize_text(text: str) -> str:
    """Collapse runs of whitespace and trim. Deterministic and pure."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _start_stage(db: Session, request: Request, stage: str) -> ProcessingRun:
    run = ProcessingRun(
        request_id=request.id,
        stage=stage,
        status=ProcessingRunStatus.STARTED,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    request.processing_status = ProcessingStatus.IN_PROGRESS
    db.flush()
    db.commit()
    return run


def _fail_stage(db: Session, request_id: uuid.UUID, run_id: uuid.UUID, exc: Exception) -> None:
    """Roll back the failed attempt, then record it as a genuine, visible
    failure — a run marked FAILED and a PROCESSING_FAILED audit entry.
    Called for both retryable and non-retryable exceptions: even a failure
    Celery is about to retry deserves an honest record of that attempt.
    """
    db.rollback()
    request = db.get(Request, request_id)
    run = db.get(ProcessingRun, run_id)

    request.processing_status = ProcessingStatus.FAILED
    run.status = ProcessingRunStatus.FAILED
    run.error_message = str(exc)
    run.completed_at = datetime.now(timezone.utc)
    db.flush()

    audit_service.record_event(
        db,
        request_id=request_id,
        event_type="PROCESSING_FAILED",
        actor="celery-worker",
        description=f"Pipeline stage failed: {exc}",
    )
    db.commit()


def mark_manual_review(db: Session, request_id: uuid.UUID, *, reason: str) -> None:
    """Called by the Celery task once retries are exhausted for a retryable
    failure (app/workers/tasks.py). Moves the *business* status to
    MANUAL_REVIEW — distinct from processing_status=FAILED, which
    `_fail_stage` already recorded for the technical failure itself."""
    request = db.get(Request, request_id)
    if request is None:
        return

    request.status = RequestStatus.MANUAL_REVIEW
    db.flush()
    audit_service.record_event(
        db,
        request_id=request_id,
        event_type="MANUAL_REVIEW_REQUIRED",
        actor="celery-worker",
        description=f"Automatic retries exhausted; routed to manual review: {reason}",
    )
    db.commit()


def run_pipeline(db: Session, request_id: uuid.UUID, ai_provider: AIProvider | None = None) -> None:
    """Public entry point. Acquires a distributed lock (app/services/locking.py)
    before doing anything else, so two workers that somehow received the same
    task can never run the pipeline for the same request concurrently — see
    locking.py's docstring for why that's a real, not theoretical, risk."""
    with pipeline_lock(request_id) as acquired:
        if not acquired:
            logger.info("processing_pipeline lock_contended request_id=%s", request_id)
            return
        _run_pipeline_locked(db, request_id, ai_provider)


def _run_pipeline_locked(db: Session, request_id: uuid.UUID, ai_provider: AIProvider | None = None) -> None:
    request = db.get(Request, request_id)
    if request is None:
        # Not a transient failure — retrying won't make a deleted/nonexistent
        # request appear. Log and stop; there's nothing to write a failure
        # record against.
        logger.warning("processing_pipeline request_not_found request_id=%s", request_id)
        return

    if request.processing_status == ProcessingStatus.COMPLETED:
        # Idempotency guard: Celery's at-least-once delivery means this task can
        # run more than once for the same request. Re-running a completed
        # pipeline would duplicate audit logs and processing_run rows for no
        # benefit, so we skip.
        logger.info("processing_pipeline already_completed request_id=%s", request_id)
        return

    ai_provider = ai_provider or get_ai_provider()

    # --- Stage 1: NORMALIZE ---
    run = _start_stage(db, request, "NORMALIZE")
    audit_service.record_event(
        db, request_id=request.id, event_type="PROCESSING_STARTED",
        actor="celery-worker", description="Async processing pipeline started",
    )
    db.commit()

    try:
        request.normalized_description = normalize_text(request.description)
        db.flush()

        run.status = ProcessingRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        audit_service.record_event(
            db, request_id=request.id, event_type="TEXT_NORMALIZED",
            actor="celery-worker", description="Description normalized",
        )
        db.commit()
    except OperationalError:
        db.rollback()
        raise
    except Exception as exc:
        _fail_stage(db, request.id, run.id, exc)
        raise

    # --- Stage 2: CLASSIFY ---
    run = _start_stage(db, request, "CLASSIFY")

    try:
        result = ai_provider.classify(request.title, request.normalized_description)

        request.category = result.category
        request.subcategory = result.subcategory
        request.priority = result.priority
        request.confidence = result.confidence
        request.summary = result.summary
        request.amount = result.amount
        for key, value in result.entities.items():
            db.add(ExtractedEntity(request_id=request.id, key=key, value=value))
        db.flush()

        run.status = ProcessingRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        audit_service.record_event(
            db, request_id=request.id, event_type="AI_CLASSIFICATION_COMPLETED",
            actor="celery-worker",
            description=f"Classified as {result.category.value} / {result.priority.value}",
            metadata={"category": result.category.value, "priority": result.priority.value, "confidence": result.confidence},
        )
        if result.entities:
            audit_service.record_event(
                db, request_id=request.id, event_type="INFORMATION_EXTRACTED",
                actor="celery-worker", description=f"Extracted {len(result.entities)} entities",
                metadata={"keys": list(result.entities.keys())},
            )
        audit_service.record_event(
            db, request_id=request.id, event_type="VALIDATION_COMPLETED",
            actor="celery-worker", description="AI output passed structured validation",
        )
        run.status = ProcessingRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except OperationalError:
        db.rollback()
        raise
    except (AIProviderError, AIOutputValidationError) as exc:
        _fail_stage(db, request.id, run.id, exc)
        raise
    except Exception as exc:
        _fail_stage(db, request.id, run.id, exc)
        raise

    # --- Stage 3: ROUTE ---
    run = _start_stage(db, request, "ROUTE")

    try:
        _route_request(db, request)

        run.status = ProcessingRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        request.processing_status = ProcessingStatus.COMPLETED
        db.flush()
        audit_service.record_event(
            db, request_id=request.id, event_type="PROCESSING_COMPLETED",
            actor="celery-worker", description="Async processing pipeline completed",
        )
        db.commit()
    except OperationalError:
        db.rollback()
        raise
    except Exception as exc:
        _fail_stage(db, request.id, run.id, exc)
        raise


def _route_request(db: Session, request: Request) -> None:
    """Deterministic validation + business rules + routing + task creation —
    the step that converts AI output into a safe, explainable business
    action. The rule engine (app/rules/engine.py), not the AI, makes this
    decision; every rule it evaluated (triggered or not) and every rule that
    actually fired is recorded so "why was this request routed here" always
    has a concrete, queryable answer.
    """
    result = evaluate_rules(db, request)

    audit_service.record_event(
        db, request_id=request.id, event_type="RULE_EVALUATION_COMPLETED",
        actor="rule-engine",
        description=f"Evaluated {len(result.evaluations)} rule(s)",
        metadata={
            "evaluations": [
                {"rule_id": e.rule_id, "rule_name": e.rule_name, "condition": e.condition,
                 "triggered": e.triggered, "action": e.action, "error": e.error}
                for e in result.evaluations
            ]
        },
    )
    for evaluation in result.triggered_evaluations:
        audit_service.record_event(
            db, request_id=request.id, event_type="RULE_TRIGGERED",
            actor="rule-engine",
            description=f'Rule "{evaluation.rule_name}" triggered: {evaluation.action}',
            metadata={"rule_id": evaluation.rule_id, "rule_name": evaluation.rule_name, "action": evaluation.action},
        )
    db.flush()

    if result.terminal_status is not None:
        request.status = result.terminal_status
        db.flush()
        audit_service.record_event(
            db, request_id=request.id, event_type="REQUEST_ROUTED",
            actor="rule-engine",
            description=f"Routed to {result.terminal_status.value} — no team assignment made",
        )
        return

    assigned_team = result.assigned_team
    if assigned_team is None:
        # No enabled rule matched at all (e.g. every default rule for this
        # category is disabled). Never leave a request silently unrouted —
        # the same "never silently lose the request" principle Phase 3
        # applies to task failures applies here to routing failures.
        request.status = RequestStatus.MANUAL_REVIEW
        db.flush()
        audit_service.record_event(
            db, request_id=request.id, event_type="MANUAL_REVIEW_REQUIRED",
            actor="rule-engine", description="No workflow rule matched this request",
        )
        return

    request.assigned_team = assigned_team
    request.status = RequestStatus.PROCESSING
    db.flush()
    audit_service.record_event(
        db, request_id=request.id, event_type="REQUEST_ROUTED",
        actor="rule-engine", description=f"Routed to {assigned_team}",
        metadata={"assigned_team": assigned_team},
    )

    task_type = _TASK_TYPE_BY_CATEGORY.get(
        request.category.value if request.category else None, "GENERAL_TASK"
    )
    if result.require_approval:
        task_type = "APPROVAL_TASK"

    task_priority = RequestPriority.HIGH if result.mark_urgent else request.priority
    task = WorkflowTask(
        request_id=request.id,
        task_type=task_type,
        assigned_team=assigned_team,
        status=TaskStatus.OPEN,
        priority=task_priority,
    )
    db.add(task)
    db.flush()

    audit_service.record_event(
        db, request_id=request.id, event_type="TASK_CREATED",
        actor="rule-engine", description=f"Created {task_type} for {assigned_team}",
        metadata={"task_id": str(task.id), "task_type": task_type, "assigned_team": assigned_team},
    )
