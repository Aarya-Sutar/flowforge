"""API -> PostgreSQL integration: proves data survives across independent
HTTP round trips against the real database, not an in-memory substitute.
This is exactly what a unit test against SQLite-in-memory cannot prove —
that test suite's "database" is thrown away between test functions by
design (see backend/tests/conftest.py), so it can never catch a bug where
something looks persisted but isn't (e.g. a forgotten db.commit()).
"""
import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_created_request_is_readable_in_a_fresh_request(api_client: httpx.Client, registered_user: dict) -> None:
    title = f"Integration test request {uuid.uuid4()}"
    create_response = api_client.post(
        "/api/requests",
        json={"title": title, "description": "Created by the integration test suite.", "department": "QA"},
        headers=registered_user["headers"],
    )
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]

    # A completely separate HTTP call — if the first request's data only
    # ever existed in application memory, this would not see it.
    fetch_response = api_client.get(f"/api/requests/{request_id}", headers=registered_user["headers"])

    assert fetch_response.status_code == 200
    assert fetch_response.json()["title"] == title


def test_duplicate_email_registration_is_rejected_by_the_real_database(
    api_client: httpx.Client, registered_user: dict
) -> None:
    # registered_user already exists in the real database — proves the
    # unique constraint (Phase 1's migration) is enforced for real, not
    # just by SQLite's looser enforcement in the unit suite.
    response = api_client.post(
        "/api/auth/register",
        json={"name": "Duplicate", "email": registered_user["email"], "password": "password123"},
    )
    assert response.status_code == 409


def test_pagination_reflects_real_row_counts(api_client: httpx.Client, registered_user: dict) -> None:
    for i in range(3):
        api_client.post(
            "/api/requests",
            json={"title": f"Pagination test {uuid.uuid4()} #{i}", "description": "x", "department": "QA"},
            headers=registered_user["headers"],
        )

    response = api_client.get("/api/requests?page=1&page_size=2", headers=registered_user["headers"])

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 3
    assert len(body["items"]) == 2
