"""The Celery application instance. Imported by both the API (to enqueue tasks)
and the worker process (to execute them) — same code, two different roles."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "flowforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Celery's "prefetch" would otherwise let one worker process grab many tasks
    # at once; with a single, potentially slow AI call per task from Phase 4
    # onward, we want each worker process handling one task at a time.
    worker_prefetch_multiplier=1,
)
