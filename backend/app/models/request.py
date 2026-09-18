"""Request ORM model — the central business entity in FlowForge."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RequestCategory(str, enum.Enum):
    IT_SUPPORT = "IT_SUPPORT"
    HR = "HR"
    FINANCE = "FINANCE"
    PROCUREMENT = "PROCUREMENT"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    ACCESS_REQUEST = "ACCESS_REQUEST"
    GENERAL = "GENERAL"


class RequestPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        Index("ix_requests_status", "status"),
        Index("ix_requests_category", "category"),
        Index("ix_requests_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    # Whitespace-collapsed, trimmed version of `description`, written by the Celery
    # worker's normalize stage (app/services/processing_service.py). Nullable because
    # it doesn't exist until that stage has actually run.
    normalized_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.PENDING
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        nullable=False,
        default=ProcessingStatus.QUEUED,
    )

    # Populated by the AI pipeline from Phase 3/4 onward. Nullable until then.
    category: Mapped[RequestCategory | None] = mapped_column(
        Enum(RequestCategory, name="request_category"), nullable=True
    )
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[RequestPriority | None] = mapped_column(
        Enum(RequestPriority, name="request_priority"), nullable=True
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Extracted by the AI layer when present (e.g. a reimbursement/purchase
    # amount) — what the FINANCE approval-threshold rule (Phase 5) checks.
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    assigned_team: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    requester = relationship("User")
    extracted_entities = relationship(
        "ExtractedEntity", back_populates="request", cascade="all, delete-orphan"
    )
    workflow_tasks = relationship(
        "WorkflowTask", back_populates="request", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="request", cascade="all, delete-orphan")
    processing_runs = relationship(
        "ProcessingRun", back_populates="request", cascade="all, delete-orphan"
    )
