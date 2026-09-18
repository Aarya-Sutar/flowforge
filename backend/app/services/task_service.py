import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.request import Request
from app.models.workflow_task import TaskStatus, WorkflowTask


def list_tasks(
    db: Session,
    *,
    status: TaskStatus | None,
    assigned_team: str | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[WorkflowTask, str]], int]:
    query = select(WorkflowTask, Request.title).join(Request, WorkflowTask.request_id == Request.id)

    if status is not None:
        query = query.where(WorkflowTask.status == status)
    if assigned_team is not None:
        query = query.where(WorkflowTask.assigned_team.ilike(f"%{assigned_team}%"))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    query = query.order_by(WorkflowTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).all()

    return [(task, title) for task, title in rows], total


def get_task(db: Session, task_id: uuid.UUID) -> WorkflowTask | None:
    return db.get(WorkflowTask, task_id)


def update_task_status(db: Session, *, task: WorkflowTask, status: TaskStatus) -> WorkflowTask:
    task.status = status
    db.commit()
    db.refresh(task)
    return task
