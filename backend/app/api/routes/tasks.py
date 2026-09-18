"""Task management — OPERATOR/ADMIN only. See Phase 2 docs for why OPERATOR
currently sees every task rather than only "assigned" ones (no per-operator
assignment exists in the data model yet, same simplification as requests)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.workflow_task import TaskStatus
from app.schemas.pagination import Page
from app.schemas.task import TaskUpdate, TaskWithRequestRead
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

staff_only = require_roles(UserRole.OPERATOR, UserRole.ADMIN)


@router.get("", response_model=Page[TaskWithRequestRead])
def list_tasks(
    db: Session = Depends(get_db),
    _current_user: User = Depends(staff_only),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    assigned_team: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[TaskWithRequestRead]:
    rows, total = task_service.list_tasks(
        db, status=status_filter, assigned_team=assigned_team, page=page, page_size=page_size
    )
    items = [
        TaskWithRequestRead(
            id=task.id, request_id=task.request_id, task_type=task.task_type,
            assigned_team=task.assigned_team, status=task.status, priority=task.priority,
            created_at=task.created_at, updated_at=task.updated_at, request_title=title,
        )
        for task, title in rows
    ]
    pages = max(1, -(-total // page_size))
    return Page(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.patch("/{task_id}", response_model=TaskWithRequestRead)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(staff_only),
) -> TaskWithRequestRead:
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    task = task_service.update_task_status(db, task=task, status=payload.status)

    return TaskWithRequestRead(
        id=task.id, request_id=task.request_id, task_type=task.task_type,
        assigned_team=task.assigned_team, status=task.status, priority=task.priority,
        created_at=task.created_at, updated_at=task.updated_at, request_title=task.request.title,
    )
