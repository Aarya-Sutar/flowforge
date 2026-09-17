"""Celery task definitions. Thin wrappers: own the DB session lifecycle and
retry policy, delegate the actual work to app/services/processing_service.py.
"""
import logging
import uuid

from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal
from app.services import processing_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="process_request",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_request(self, request_id: str) -> None:
    """Entry point the API enqueues via `process_request.delay(str(request.id))`.

    Retries only on OperationalError (transient DB connectivity issues) —
    a request that fails for any other reason is a real failure, not
    something a retry can fix, so it's recorded as FAILED instead.
    """
    logger.info("celery_task_started task=process_request request_id=%s attempt=%s", request_id, self.request.retries + 1)

    db = SessionLocal()
    try:
        processing_service.run_pipeline(db, uuid.UUID(request_id))
    finally:
        db.close()

    logger.info("celery_task_finished task=process_request request_id=%s", request_id)
