"""A Redis-backed distributed lock protecting a single request's pipeline
run from concurrent execution.

Why this exists: Celery guarantees *at-least-once* delivery, not *exactly-
once*. In rare cases (a worker crashes after starting a task but before
Celery's broker marks it acknowledged, a broker visibility-timeout
redelivery under load) the *same* task can be picked up by two worker
processes at nearly the same moment. Phase 3's idempotency guard in
processing_service.run_pipeline only checks "is this already COMPLETED?"
once, at the very start — it does nothing to stop two workers from both
passing that check before either has committed anything, then both
proceeding to run NORMALIZE/CLASSIFY/ROUTE concurrently against the same
row. That would produce duplicated ProcessingRun rows, duplicated audit
log entries, and a final state determined by whichever commit happened to
land last — silently wrong, not just inefficient.

A lock closes that window: only the worker that acquires it proceeds: the
other backs off, trusting the lock holder to finish the job.
"""
import logging
import uuid
from contextlib import contextmanager

import redis as redis_lib

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

_LOCK_PREFIX = "flowforge:pipeline-lock:"
# Safety valve: if a worker crashes while holding the lock, it must not be
# held forever. Long enough for a real (if slow) AI provider call plus
# retries; short enough that a genuinely stuck lock clears on its own.
_LOCK_TTL_SECONDS = 300


@contextmanager
def pipeline_lock(request_id: uuid.UUID):
    """Yields True if the lock was acquired (caller should proceed) or False
    if another worker already holds it (caller should skip — the other
    worker is expected to complete the run). Always releases on exit if it
    was the one holding the lock.
    """
    key = f"{_LOCK_PREFIX}{request_id}"

    try:
        acquired = bool(redis_client.set(key, "1", nx=True, ex=_LOCK_TTL_SECONDS))
    except redis_lib.exceptions.RedisError as exc:
        # Fail OPEN, not closed: a Redis outage should degrade FlowForge's
        # duplicate-processing protection, not take down request processing
        # entirely. This is a deliberate availability-over-strict-correctness
        # trade-off — documented in docs/learning/PHASE_7_PRODUCTION_ENGINEERING.md
        # — and it's also what lets the test suite run with no Redis at all,
        # the same "zero external dependencies" principle from Phase 1.
        logger.warning("pipeline_lock_unavailable request_id=%s error=%s", request_id, exc)
        yield True
        return

    if not acquired:
        logger.warning("pipeline_lock_contended request_id=%s", request_id)

    try:
        yield acquired
    finally:
        if acquired:
            try:
                redis_client.delete(key)
            except redis_lib.exceptions.RedisError:
                pass  # TTL will expire it regardless
