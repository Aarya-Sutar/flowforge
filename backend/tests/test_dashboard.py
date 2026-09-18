from fastapi.testclient import TestClient


def create_request(client: TestClient, headers: dict, title: str = "Test"):
    return client.post(
        "/api/requests",
        json={"title": title, "description": "Some description here.", "department": "Engineering"},
        headers=headers,
    )


def test_summary_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/dashboard/summary").status_code == 401


def test_summary_counts_own_requests_for_regular_user(client: TestClient, user_a_headers: dict, user_b_headers: dict) -> None:
    create_request(client, user_a_headers, "A's request")
    create_request(client, user_b_headers, "B's request")

    response = client.get("/api/dashboard/summary", headers=user_a_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_summary_counts_all_requests_for_admin(client: TestClient, user_a_headers: dict, user_b_headers: dict, admin_headers: dict) -> None:
    create_request(client, user_a_headers)
    create_request(client, user_b_headers)

    response = client.get("/api/dashboard/summary", headers=admin_headers)

    assert response.json()["total"] == 2


def test_summary_has_no_average_when_nothing_completed(client: TestClient, admin_headers: dict) -> None:
    response = client.get("/api/dashboard/summary", headers=admin_headers)
    assert response.json()["average_processing_time_seconds"] is None


def test_metrics_returns_expected_shape(client: TestClient, user_a_headers: dict, admin_headers: dict) -> None:
    create_request(client, user_a_headers)

    response = client.get("/api/dashboard/metrics", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert "requests_by_category" in body
    assert "requests_by_status" in body
    assert "priority_distribution" in body
    assert "requests_over_time" in body
