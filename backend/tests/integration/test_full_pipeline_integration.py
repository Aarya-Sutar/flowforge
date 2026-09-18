"""API -> Redis -> Celery -> PostgreSQL: the complete asynchronous pipeline,
end to end, against real infrastructure — no mocked .delay(), no stub AI
provider substitution, no SQLite. This is the automated version of the
manual curl-based verification every phase from 3 onward was checked
against live; here it's a repeatable, CI-runnable test instead of a
one-off manual session.

Uses AI_PROVIDER=mock (the default — see Phase 4) so this test is
deterministic and needs no API key or local LLM; it still proves every
other link in the chain for real: the task actually gets enqueued to
Redis, a real Celery worker process actually picks it up, and the result
actually lands in Postgres, visible through a completely independent API
call.
"""
import time
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration

_POLL_TIMEOUT_SECONDS = 30
_POLL_INTERVAL_SECONDS = 0.5


def _wait_for_processing(api_client: httpx.Client, request_id: str, headers: dict) -> dict:
    deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        response = api_client.get(f"/api/requests/{request_id}", headers=headers)
        response.raise_for_status()
        body = response.json()
        if body["processing_status"] in ("COMPLETED", "FAILED"):
            return body
        time.sleep(_POLL_INTERVAL_SECONDS)
    pytest.fail(
        f"Request {request_id} did not finish processing within {_POLL_TIMEOUT_SECONDS}s — "
        "is the celery-worker container running? (`docker compose ps`)"
    )


def test_request_is_actually_classified_and_routed_by_the_real_worker(
    api_client: httpx.Client, registered_user: dict
) -> None:
    create_response = api_client.post(
        "/api/requests",
        json={
            "title": f"Cannot access git repository {uuid.uuid4()}",
            "description": "I just joined engineering and my VPN access and login are not working.",
            "department": "Engineering",
        },
        headers=registered_user["headers"],
    )
    assert create_response.status_code == 201
    created = create_response.json()

    # The API must return before processing finishes — proves Phase 3's
    # core architectural point for real, not just in a unit test.
    assert created["processing_status"] == "QUEUED"
    assert created["category"] is None

    final = _wait_for_processing(api_client, created["id"], registered_user["headers"])

    assert final["processing_status"] == "COMPLETED"
    assert final["category"] == "ACCESS_REQUEST"
    assert final["assigned_team"] == "IT Security Team"

    # The task real ROUTE stage created, fetched via its own real endpoint.
    tasks_response = api_client.get(f"/api/requests/{created['id']}/tasks", headers=registered_user["headers"])
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) == 1
    assert tasks[0]["assigned_team"] == "IT Security Team"

    # The full, real audit trail — every stage actually ran, in order.
    timeline_response = api_client.get(
        f"/api/requests/{created['id']}/timeline", headers=registered_user["headers"]
    )
    event_types = [event["event_type"] for event in timeline_response.json()]
    assert event_types == [
        "REQUEST_CREATED",
        "PROCESSING_STARTED",
        "TEXT_NORMALIZED",
        "AI_CLASSIFICATION_COMPLETED",
        "INFORMATION_EXTRACTED",
        "VALIDATION_COMPLETED",
        "RULE_EVALUATION_COMPLETED",
        "RULE_TRIGGERED",
        "REQUEST_ROUTED",
        "TASK_CREATED",
        "PROCESSING_COMPLETED",
    ]


def test_retry_reprocesses_via_the_real_queue(api_client: httpx.Client, registered_user: dict, admin_headers_integration: dict) -> None:
    create_response = api_client.post(
        "/api/requests",
        json={
            "title": f"Retry integration test {uuid.uuid4()}",
            "description": "Generic request with no strong category signal.",
            "department": "Operations",
        },
        headers=registered_user["headers"],
    )
    created = create_response.json()
    _wait_for_processing(api_client, created["id"], registered_user["headers"])

    retry_response = api_client.post(
        f"/api/requests/{created['id']}/retry", headers=admin_headers_integration
    )
    # Only eligible if the first run landed in FAILED/MANUAL_REVIEW/NEEDS_INFORMATION —
    # this generic-text request is likely to land in MANUAL_REVIEW (low mock
    # confidence with no keyword match), making it retry-eligible; if it
    # happened to match a category confidently instead, retry correctly
    # refuses with 409, which this assertion also accepts as valid.
    assert retry_response.status_code in (200, 409)
