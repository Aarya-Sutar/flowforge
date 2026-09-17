from fastapi.testclient import TestClient


def test_health_check_reports_ok_when_database_reachable(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
