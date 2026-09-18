"""Tests the distributed lock in isolation, using fakeredis (an in-memory
Redis simulation — no live Redis server needed, keeping this test as
dependency-free as the rest of the suite) plus a monkeypatched failure case
to prove the fail-open behavior specifically."""
import uuid

import fakeredis
import pytest
import redis as redis_lib

from app.services import locking


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(locking, "redis_client", fake)
    return fake


def test_lock_is_acquired_when_free() -> None:
    with locking.pipeline_lock(uuid.uuid4()) as acquired:
        assert acquired is True


def test_lock_blocks_concurrent_acquisition(fake_redis: fakeredis.FakeRedis) -> None:
    request_id = uuid.uuid4()
    key = f"flowforge:pipeline-lock:{request_id}"
    fake_redis.set(key, "1")  # simulate another worker already holding it

    with locking.pipeline_lock(request_id) as acquired:
        assert acquired is False


def test_lock_is_released_after_context_exits(fake_redis: fakeredis.FakeRedis) -> None:
    request_id = uuid.uuid4()
    key = f"flowforge:pipeline-lock:{request_id}"

    with locking.pipeline_lock(request_id):
        assert fake_redis.get(key) is not None

    assert fake_redis.get(key) is None


def test_lock_is_released_even_if_the_body_raises(fake_redis: fakeredis.FakeRedis) -> None:
    request_id = uuid.uuid4()
    key = f"flowforge:pipeline-lock:{request_id}"

    with pytest.raises(ValueError):
        with locking.pipeline_lock(request_id):
            raise ValueError("boom")

    assert fake_redis.get(key) is None


def test_lock_fails_open_when_redis_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenRedis:
        def set(self, *args, **kwargs):
            raise redis_lib.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(locking, "redis_client", BrokenRedis())

    with locking.pipeline_lock(uuid.uuid4()) as acquired:
        assert acquired is True  # degraded, but processing still proceeds
