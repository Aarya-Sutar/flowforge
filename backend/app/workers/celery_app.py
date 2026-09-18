"""The Celery application instance. Imported by both the API (to enqueue tasks)
and the worker process (to execute them) — same code, two different roles."""
import sys

from celery import Celery

from app.core.config import settings

# Distinguishes "this process is the `celery worker` command" from "this
# process is uvicorn running the API" — both import this same module, but
# they need different broker-connection-retry behavior (see the
# broker_connection_max_retries comment below).
_IS_WORKER_PROCESS = "worker" in sys.argv

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
    # Bounds how long any single connection attempt can take (confirmed
    # directly: a raw redis-py connection with these settings fails in ~4s
    # when the broker is unreachable, instead of hanging indefinitely).
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    # How many times to retry *establishing* the broker connection before
    # giving up — this is the setting that actually controls how long
    # POST /api/requests hangs when Redis is unreachable (NOT
    # apply_async's retry_policy, which only governs retrying the publish
    # once a connection already exists — see app/api/routes/requests.py's
    # _enqueue_processing for that separate, narrower mechanism, and Phase
    # 7's learning doc for the full live investigation that found this).
    #
    # This has to differ by role, which is why it's conditional rather than
    # a flat value: a low number is exactly right for the API (producer) —
    # fail the HTTP request fast rather than hang for minutes. The same low
    # number is actively harmful for the worker (consumer)'s long-lived
    # connection — live-verified in Phase 7: setting it globally to 2 made
    # the worker give up and exit after a brief Redis outage instead of
    # patiently reconnecting once Redis came back, taking the whole
    # pipeline down until someone manually restarted the container. Celery's
    # default (100, effectively "keep trying") is correct for the worker.
    broker_connection_max_retries=2 if not _IS_WORKER_PROCESS else 100,
)
