"""Tests /api/tasks. Requests created via the client fixture never actually
run the pipeline (Celery's .delay is mocked to a no-op — see conftest.py),
so tasks are seeded directly against the db_session here, the same way
test_processing_service.py's ROUTE stage tests do."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.request import ProcessingStatus, Request, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_task import TaskStatus, WorkflowTask


def _make_request_with_task(db_session: Session, *, team: str = "IT Team", task_status: TaskStatus = TaskStatus.OPEN) -> WorkflowTask:
    user = User(name="Requester", email=f"{uuid.uuid4()}@example.com", password_hash=hash_password("password123"), role=UserRole.USER)
    db_session.add(user)
    db_session.commit()

    request = Request(
        requester_id=user.id, title="Sample task request", description="desc", department="Engineering",
        status=RequestStatus.PROCESSING, processing_status=ProcessingStatus.COMPLETED,
    )
    db_session.add(request)
    db_session.commit()

    task = WorkflowTask(request_id=request.id, task_type="IT_TASK", assigned_team=team, status=task_status)
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def test_list_tasks_requires_staff_role(client: TestClient, user_a_headers: dict) -> None:
    assert client.get("/api/tasks", headers=user_a_headers).status_code == 403


def test_admin_can_list_tasks(client: TestClient, db_session: Session, admin_headers: dict) -> None:
    _make_request_with_task(db_session)

    response = client.get("/api/tasks", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["request_title"] == "Sample task request"


def test_operator_can_list_tasks(client: TestClient, db_session: Session, operator_headers: dict) -> None:
    _make_request_with_task(db_session)
    assert client.get("/api/tasks", headers=operator_headers).status_code == 200


def test_filter_tasks_by_status(client: TestClient, db_session: Session, admin_headers: dict) -> None:
    _make_request_with_task(db_session, task_status=TaskStatus.OPEN)
    _make_request_with_task(db_session, task_status=TaskStatus.DONE)

    response = client.get("/api/tasks?status=DONE", headers=admin_headers)

    assert response.json()["total"] == 1


def test_filter_tasks_by_team(client: TestClient, db_session: Session, admin_headers: dict) -> None:
    _make_request_with_task(db_session, team="HR Team")
    _make_request_with_task(db_session, team="IT Team")

    response = client.get("/api/tasks?assigned_team=HR", headers=admin_headers)

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["assigned_team"] == "HR Team"


def test_admin_can_update_task_status(client: TestClient, db_session: Session, admin_headers: dict) -> None:
    task = _make_request_with_task(db_session)

    response = client.patch(f"/api/tasks/{task.id}", json={"status": "IN_PROGRESS"}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_update_nonexistent_task_returns_404(client: TestClient, admin_headers: dict) -> None:
    response = client.patch(
        "/api/tasks/00000000-0000-0000-0000-000000000000", json={"status": "DONE"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_regular_user_cannot_update_task(client: TestClient, db_session: Session, user_a_headers: dict) -> None:
    task = _make_request_with_task(db_session)

    response = client.patch(f"/api/tasks/{task.id}", json={"status": "DONE"}, headers=user_a_headers)

    assert response.status_code == 403
