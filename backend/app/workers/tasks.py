"""Celery task definitions. Thin wrappers: own the DB session lifecycle and
retry policy, delegate the actual work to app/services/processing_service.py.
"""
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.exc import OperationalError

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.core.database import SessionLocal
from app.services import processing_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="process_request",
    # OperationalError (DB connectivity) retries automatically via this
    # decorator — there's no application decision to make, just "wait and
    # try again." AI failures are handled explicitly in the body below,
    # because a decision (retry vs. give up and route to a human) has to be
    # made once retries run out — autoretry_for alone can't express that.
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_request(self, request_id: str) -> None:
    logger.info(
        "celery_task_started task=process_request request_id=%s attempt=%s",
        request_id, self.request.retries + 1,
    )

    db = SessionLocal()
    try:
        processing_service.run_pipeline(db, uuid.UUID(request_id))
    except (AIProviderError, AIOutputValidationError) as exc:
        # Same retry budget as the decorator's max_retries (self.request.retries
        # is one shared counter for this task, regardless of what caused each
        # retry) — but here we get a chance to act once it's exhausted, instead
        # of just letting Celery mark the task FAILED with nothing to show for it.
        try:
            backoff_seconds = min(2 ** self.request.retries * 5, 60)
            logger.warning(
                "celery_task_ai_failure_retrying request_id=%s attempt=%s reason=%s",
                request_id, self.request.retries + 1, exc,
            )
            raise self.retry(exc=exc, countdown=backoff_seconds)
        except MaxRetriesExceededError:
            logger.error(
                "celery_task_ai_retries_exhausted request_id=%s reason=%s", request_id, exc
            )
            processing_service.mark_manual_review(db, uuid.UUID(request_id), reason=str(exc))
    finally:
        db.close()

    logger.info("celery_task_finished task=process_request request_id=%s", request_id)
