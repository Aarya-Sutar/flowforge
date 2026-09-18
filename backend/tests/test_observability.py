"""Tests for Phase 7's production-engineering additions: rate limiting,
centralized exception handling, and the request-ID/logging middleware."""
import asyncio

from fastapi.testclient import TestClient


def test_response_includes_request_id_header(client: TestClient) -> None:
    response = client.get("/api/health")
    assert "X-Request-ID" in response.headers


def test_request_id_is_echoed_back_when_client_supplies_one(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "test-fixed-id-123"})
    assert response.headers["X-Request-ID"] == "test-fixed-id-123"


def test_login_is_rate_limited_after_repeated_attempts(client: TestClient) -> None:
    payload = {"email": "nobody@example.com", "password": "wrong-password"}

    responses = [client.post("/api/auth/login", json=payload) for _ in range(15)]

    assert any(r.status_code == 429 for r in responses)


def test_register_is_rate_limited_after_repeated_attempts(client: TestClient) -> None:
    responses = []
    for i in range(15):
        responses.append(
            client.post(
                "/api/auth/register",
                json={"name": "Spammer", "email": f"spam{i}@example.com", "password": "password123"},
            )
        )

    assert any(r.status_code == 429 for r in responses)


def test_unhandled_exception_handler_returns_generic_message_not_internals() -> None:
    """Exercises app.main.unhandled_exception_handler directly — reaching it
    via a real broken route would require mutating the shared, module-level
    `app` object mid-test-suite, which risks leaking into other tests. This
    tests the handler's actual behavior just as precisely, in isolation."""
    from starlette.requests import Request as StarletteRequest

    from app.main import unhandled_exception_handler

    scope = {"type": "http", "method": "GET", "path": "/api/whatever", "headers": []}
    request = StarletteRequest(scope)
    request.state.request_id = "test-request-id"

    exc = RuntimeError("a deliberately unexpected internal failure with sensitive detail")

    response = asyncio.run(unhandled_exception_handler(request, exc))

    assert response.status_code == 500
    body = response.body.decode()
    assert "sensitive detail" not in body
    assert "Traceback" not in body
    assert "An unexpected error occurred" in body
