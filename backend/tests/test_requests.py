import uuid

from fastapi.testclient import TestClient

from app.models.request import ProcessingStatus, Request, RequestStatus


def create_request(client: TestClient, headers: dict, title: str = "Cannot access repo", department: str = "Engineering"):
    return client.post(
        "/api/requests",
        json={"title": title, "description": "I cannot access the internal git repository.", "department": department},
        headers=headers,
    )


def test_create_request_sets_initial_state(client: TestClient, user_a_headers: dict) -> None:
    response = create_request(client, user_a_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["processing_status"] == "QUEUED"
    assert body["category"] is None
    assert body["title"] == "Cannot access repo"


def test_create_request_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/requests",
        json={"title": "x", "description": "y", "department": "Engineering"},
    )
    assert response.status_code == 401


def test_create_request_writes_audit_log(client: TestClient, user_a_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    timeline = client.get(f"/api/requests/{created['id']}/timeline", headers=user_a_headers)

    assert timeline.status_code == 200
    events = timeline.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "REQUEST_CREATED"


def test_user_can_retrieve_own_request(client: TestClient, user_a_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.get(f"/api/requests/{created['id']}", headers=user_a_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_user_cannot_retrieve_another_users_request(
    client: TestClient, user_a_headers: dict, user_b_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.get(f"/api/requests/{created['id']}", headers=user_b_headers)

    assert response.status_code == 404


def test_operator_can_retrieve_any_request(
    client: TestClient, user_a_headers: dict, operator_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.get(f"/api/requests/{created['id']}", headers=operator_headers)

    assert response.status_code == 200


def test_get_nonexistent_request_returns_404(client: TestClient, user_a_headers: dict) -> None:
    response = client.get(
        "/api/requests/00000000-0000-0000-0000-000000000000", headers=user_a_headers
    )
    assert response.status_code == 404


def test_list_requests_only_shows_own_for_regular_user(
    client: TestClient, user_a_headers: dict, user_b_headers: dict
) -> None:
    create_request(client, user_a_headers, title="A's request")
    create_request(client, user_b_headers, title="B's request")

    response = client.get("/api/requests", headers=user_a_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "A's request"


def test_list_requests_shows_all_for_admin(
    client: TestClient, user_a_headers: dict, user_b_headers: dict, admin_headers: dict
) -> None:
    create_request(client, user_a_headers)
    create_request(client, user_b_headers)

    response = client.get("/api/requests", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_list_requests_pagination(client: TestClient, admin_headers: dict, user_a_headers: dict) -> None:
    for i in range(5):
        create_request(client, user_a_headers, title=f"Request {i}")

    response = client.get("/api/requests?page=1&page_size=2", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["pages"] == 3
    assert len(body["items"]) == 2


def test_list_requests_filter_by_department(
    client: TestClient, admin_headers: dict, user_a_headers: dict
) -> None:
    create_request(client, user_a_headers, department="Engineering")
    create_request(client, user_a_headers, department="Sales")

    response = client.get("/api/requests?department=Engineering", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["department"] == "Engineering"


def test_list_requests_sort_order(client: TestClient, admin_headers: dict, user_a_headers: dict) -> None:
    create_request(client, user_a_headers, title="First")
    create_request(client, user_a_headers, title="Second")

    response = client.get("/api/requests?sort_by=created_at&sort_order=asc", headers=admin_headers)

    titles = [item["title"] for item in response.json()["items"]]
    assert titles == ["First", "Second"]


def test_owner_can_update_own_pending_request(client: TestClient, user_a_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.patch(
        f"/api/requests/{created['id']}", json={"title": "Updated title"}, headers=user_a_headers
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"


def test_owner_cannot_change_status(client: TestClient, user_a_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.patch(
        f"/api/requests/{created['id']}", json={"status": "COMPLETED"}, headers=user_a_headers
    )

    assert response.status_code == 403


def test_admin_can_change_status(client: TestClient, user_a_headers: dict, admin_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.patch(
        f"/api/requests/{created['id']}", json={"status": "COMPLETED"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


def test_request_tasks_endpoint_returns_empty_list_initially(
    client: TestClient, user_a_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.get(f"/api/requests/{created['id']}/tasks", headers=user_a_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_create_request_leaves_processing_status_queued(client: TestClient, user_a_headers: dict) -> None:
    # process_request.delay is mocked to a no-op in tests (see conftest.py), so
    # the pipeline never actually runs here — this only checks the state the API
    # itself commits before handing off to the (mocked) queue.
    created = create_request(client, user_a_headers).json()
    assert created["processing_status"] == "QUEUED"


def test_retry_rejected_when_not_failed(client: TestClient, user_a_headers: dict, admin_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.post(f"/api/requests/{created['id']}/retry", headers=admin_headers)

    assert response.status_code == 409


def test_retry_rejected_for_regular_user(client: TestClient, user_a_headers: dict) -> None:
    created = create_request(client, user_a_headers).json()

    response = client.post(f"/api/requests/{created['id']}/retry", headers=user_a_headers)

    assert response.status_code == 403


def test_retry_requeues_a_failed_request(
    client: TestClient, db_session, user_a_headers: dict, admin_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()
    # processing_status isn't client-settable via the API (only the real
    # pipeline sets it to FAILED) — set it directly to simulate that outcome.
    request_row = db_session.get(Request, uuid.UUID(created["id"]))
    request_row.processing_status = ProcessingStatus.FAILED
    db_session.commit()

    response = client.post(f"/api/requests/{created['id']}/retry", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "QUEUED"

    timeline = client.get(f"/api/requests/{created['id']}/timeline", headers=admin_headers).json()
    assert any(event["event_type"] == "PROCESSING_RETRIED" for event in timeline)


def test_retry_allowed_for_manual_review_request(
    client: TestClient, db_session, user_a_headers: dict, admin_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()
    request_row = db_session.get(Request, uuid.UUID(created["id"]))
    request_row.status = RequestStatus.MANUAL_REVIEW
    request_row.processing_status = ProcessingStatus.COMPLETED  # pipeline succeeded; outcome needs review
    db_session.commit()

    response = client.post(f"/api/requests/{created['id']}/retry", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["processing_status"] == "QUEUED"


def test_retry_allowed_for_needs_information_request(
    client: TestClient, db_session, user_a_headers: dict, admin_headers: dict
) -> None:
    created = create_request(client, user_a_headers).json()
    request_row = db_session.get(Request, uuid.UUID(created["id"]))
    request_row.status = RequestStatus.NEEDS_INFORMATION
    request_row.processing_status = ProcessingStatus.COMPLETED
    db_session.commit()

    response = client.post(f"/api/requests/{created['id']}/retry", headers=admin_headers)

    assert response.status_code == 200
