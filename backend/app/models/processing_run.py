"""One row per pipeline stage attempt (Phase 3+). Powers retry/failure diagnostics."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProcessingRunStatus(str, enum.Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # e.g. "CLASSIFICATION", "EXTRACTION", "VALIDATION", "ROUTING" — grows each phase,
    # same reasoning as AuditLog.event_type for why this isn't a Postgres ENUM.
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ProcessingRunStatus] = mapped_column(
        Enum(ProcessingRunStatus, name="processing_run_status"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request = relationship("Request", back_populates="processing_runs")
