import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    condition: str = Field(min_length=1)
    action: str = Field(min_length=1)
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    condition: str | None = Field(default=None, min_length=1)
    action: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    condition: str
    action: str
    enabled: bool
    created_at: datetime
