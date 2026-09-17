from fastapi.testclient import TestClient


def create_rule(client: TestClient, headers: dict, name: str = "High priority IT"):
    return client.post(
        "/api/rules",
        json={
            "name": name,
            "description": "Escalate high priority IT requests",
            "category": "IT_SUPPORT",
            "condition": "priority == HIGH",
            "action": "assign_team = IT_ESCALATION",
            "enabled": True,
        },
        headers=headers,
    )


def test_admin_can_create_rule(client: TestClient, admin_headers: dict) -> None:
    response = create_rule(client, admin_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "High priority IT"
    assert body["enabled"] is True


def test_regular_user_cannot_create_rule(client: TestClient, user_a_headers: dict) -> None:
    response = create_rule(client, user_a_headers)
    assert response.status_code == 403


def test_regular_user_cannot_list_rules(client: TestClient, user_a_headers: dict) -> None:
    response = client.get("/api/rules", headers=user_a_headers)
    assert response.status_code == 403


def test_admin_can_list_rules(client: TestClient, admin_headers: dict) -> None:
    create_rule(client, admin_headers)

    response = client.get("/api/rules", headers=admin_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_admin_can_update_rule(client: TestClient, admin_headers: dict) -> None:
    created = create_rule(client, admin_headers).json()

    response = client.patch(
        f"/api/rules/{created['id']}", json={"enabled": False}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_update_nonexistent_rule_returns_404(client: TestClient, admin_headers: dict) -> None:
    response = client.patch(
        "/api/rules/00000000-0000-0000-0000-000000000000",
        json={"enabled": False},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_operator_cannot_manage_rules(client: TestClient, operator_headers: dict) -> None:
    response = client.get("/api/rules", headers=operator_headers)
    assert response.status_code == 403
