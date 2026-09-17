"""Writes audit trail entries. Every important state transition goes through here."""
import uuid

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
    )
    db.add(entry)
    db.flush()
    return entry
