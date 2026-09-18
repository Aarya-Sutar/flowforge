import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.request import RequestPriority
from app.models.workflow_task import TaskStatus


class TaskUpdate(BaseModel):
    status: TaskStatus


class TaskWithRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    task_type: str
    assigned_team: str
    status: TaskStatus
    priority: RequestPriority | None
    created_at: datetime
    updated_at: datetime
    request_title: str
