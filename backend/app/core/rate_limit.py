"""Rate limiting for sensitive endpoints (spec: "Add rate limiting to
sensitive endpoints if it can be implemented cleanly") — login and register
specifically, since those are what credential-stuffing/brute-force attempts
and registration-spam bots actually target.

Uses in-memory storage, which is the right amount of complexity for how
this app actually runs today: a single backend process/container, not a
horizontally-scaled fleet. In-memory means each process enforces its own
limit independently — correct and sufficient at 1 replica, and it keeps
rate limiting from adding a hard Redis dependency to every request (the
same "don't make a feature's failure mode worse than the problem it
solves" reasoning as the fail-open pipeline lock in locking.py). If
FlowForge is ever actually scaled to multiple backend replicas, this
should move to Redis-backed storage (`storage_uri=settings.CELERY_BROKER_URL`)
so the limit is shared correctly across all of them — documented here
rather than built now, since nothing today needs it yet.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
