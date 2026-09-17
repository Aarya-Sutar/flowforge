from fastapi.testclient import TestClient


def register_user(client: TestClient, email: str = "jane@example.com", password: str = "supersecret1"):
    return client.post(
        "/api/auth/register",
        json={"name": "Jane Doe", "email": email, "password": password},
    )


def test_register_creates_a_user(client: TestClient) -> None:
    response = register_user(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["role"] == "USER"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_user(client)
    response = register_user(client)

    assert response.status_code == 409


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"name": "Jane Doe", "email": "jane@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_login_returns_a_token_for_valid_credentials(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_rejects_wrong_password(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )

    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client: TestClient) -> None:
    register_user(client)
    login_response = client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )
    token = login_response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "jane@example.com"


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
