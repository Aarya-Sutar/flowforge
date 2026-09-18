"""Fixtures for the integration suite.

Unlike the rest of the test suite (SQLite in-memory, Celery's .delay
mocked — see backend/tests/conftest.py), these tests hit the REAL,
already-running Docker Compose stack over real HTTP: real FastAPI, real
PostgreSQL, real Redis, a real Celery worker actually picking up and
processing tasks. They prove the wiring the unit suite structurally
cannot — see docs/learning/PHASE_7_PRODUCTION_ENGINEERING.md for why
both kinds of tests are needed and what each one catches.

Requires: `docker compose up -d` running first. If the stack isn't
reachable, every test here skips with a clear reason rather than failing
with a confusing connection error.
"""
import os
import uuid

import httpx
import pytest

INTEGRATION_API_URL = os.environ.get("INTEGRATION_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    try:
        response = httpx.get(f"{INTEGRATION_API_URL}/api/health", timeout=3)
        response.raise_for_status()
        if response.json().get("database") != "up":
            pytest.skip("Backend is reachable but reports its database is down")
    except httpx.HTTPError:
        pytest.skip(
            f"Integration tests require a live stack at {INTEGRATION_API_URL} "
            "— run `docker compose up -d` first."
        )
    return INTEGRATION_API_URL


@pytest.fixture()
def api_client(api_base_url: str):
    with httpx.Client(base_url=api_base_url, timeout=10) as client:
        yield client


@pytest.fixture()
def admin_headers_integration(api_client: httpx.Client) -> dict:
    """Logs in as the seeded admin account (backend/app/seed.py) — there's no
    self-service way to become an ADMIN (by design, see Phase 2), so tests
    needing admin access rely on the seed script having been run. Skips
    with a clear reason rather than failing confusingly if it hasn't."""
    response = api_client.post(
        "/api/auth/login", json={"email": "admin@flowforge.dev", "password": "password123"}
    )
    if response.status_code != 200:
        pytest.skip(
            "Seeded admin account not found — run `docker compose exec backend python -m app.seed` first."
        )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def registered_user(api_client: httpx.Client) -> dict:
    """Registers a brand-new user with a unique email (this hits the real,
    persistent database — reusing a fixed email across test runs would
    collide with a previous run's leftover data)."""
    email = f"integration-{uuid.uuid4()}@example.com"
    password = "integration-test-password-1"

    register_response = api_client.post(
        "/api/auth/register", json={"name": "Integration Test User", "email": email, "password": password}
    )
    register_response.raise_for_status()

    login_response = api_client.post("/api/auth/login", json={"email": email, "password": password})
    login_response.raise_for_status()
    token = login_response.json()["access_token"]

    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
