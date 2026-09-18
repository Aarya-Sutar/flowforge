"""A single shared Redis client, reused for both the distributed pipeline
lock (app/services/locking.py) and the rate limiter's storage backend
(app/main.py). Separate from Celery's own Redis connection (Celery manages
that internally) — this is app code talking to Redis directly.
"""
import redis

from app.core.config import settings

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
