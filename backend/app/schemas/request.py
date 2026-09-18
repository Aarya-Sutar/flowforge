"""Pydantic schemas for the requests API."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.request import ProcessingStatus, RequestCategory, RequestPriority, RequestStatus


class RequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    department: str = Field(min_length=1, max_length=100)


class RequestUpdate(BaseModel):
    """All fields optional: a PATCH only touches what's provided."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    department: str | None = Field(default=None, min_length=1, max_length=100)
    status: RequestStatus | None = None


class ExtractedEntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    title: str
    description: str
    normalized_description: str | None
    department: str
    status: RequestStatus
    processing_status: ProcessingStatus
    category: RequestCategory | None
    subcategory: str | None
    priority: RequestPriority | None
    confidence: float | None
    amount: float | None
    assigned_team: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime


class RequestDetailRead(RequestRead):
    extracted_entities: list[ExtractedEntityRead] = []
