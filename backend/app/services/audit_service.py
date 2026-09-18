"""Writes audit trail entries. Every important state transition goes through here."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_event(
    db: Session,
    *,
    request_id: uuid.UUID,
    event_type: str,
    actor: str,
    description: str,
    metadata: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        request_id=request_id,
        event_type=event_type,
        actor=actor,
        description=description,
        event_metadata=metadata,
        # Set explicitly rather than relying on the column's server_default
        # (Postgres func.now()): now() returns the *transaction's* start
        # time, identical for every statement in that transaction — several
        # events written within one pipeline stage's commit would otherwise
        # all get the exact same timestamp, making their relative order in
        # the timeline undefined. A Python-side timestamp, taken at the
        # moment each event is actually recorded, avoids that.
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry
