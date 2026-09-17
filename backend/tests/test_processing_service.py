"""Tests the pipeline logic directly against a Session — no Celery, no broker,
no HTTP. This is exactly why app/services/processing_service.py is a separate,
plain function from app/workers/tasks.py's Celery-bound wrapper."""
import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.request import ProcessingStatus, Request, RequestStatus
from app.models.user import User, UserRole
from app.services import processing_service
from app.core.security import hash_password


def _make_request(db_session: Session, description: str = "  I   cannot   access   the repo.  ") -> Request:
    user = User(name="Requester", email=f"{uuid.uuid4()}@example.com", password_hash=hash_password("password123"), role=UserRole.USER)
    db_session.add(user)
    db_session.commit()

    request = Request(
        requester_id=user.id,
        title="Access issue",
        description=description,
        department="Engineering",
        status=RequestStatus.PENDING,
        processing_status=ProcessingStatus.QUEUED,
    )
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)
    return request


def test_normalize_text_collapses_whitespace() -> None:
    assert processing_service.normalize_text("  hello   world  \n\tfoo  ") == "hello world foo"


def test_run_pipeline_normalizes_description(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.run_pipeline(db_session, request.id)

    db_session.refresh(request)
    assert request.normalized_description == "I cannot access the repo."


def test_run_pipeline_marks_processing_completed(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.run_pipeline(db_session, request.id)

    db_session.refresh(request)
    assert request.processing_status == ProcessingStatus.COMPLETED
    # Phase 3 has no classification/routing yet — business status must not
    # silently advance just because the (current, partial) pipeline finished.
    assert request.status == RequestStatus.PENDING


def test_run_pipeline_creates_processing_run_row(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.run_pipeline(db_session, request.id)

    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).all()
    assert len(runs) == 1
    assert runs[0].stage == "NORMALIZE"
    assert runs[0].status == ProcessingRunStatus.SUCCEEDED
    assert runs[0].completed_at is not None


def test_run_pipeline_writes_expected_audit_events(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.run_pipeline(db_session, request.id)

    events = [
        log.event_type
        for log in db_session.query(AuditLog).filter(AuditLog.request_id == request.id).order_by(AuditLog.created_at)
    ]
    assert events == ["PROCESSING_STARTED", "TEXT_NORMALIZED", "PROCESSING_COMPLETED"]


def test_run_pipeline_is_idempotent(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.run_pipeline(db_session, request.id)
    processing_service.run_pipeline(db_session, request.id)  # simulates Celery redelivery

    events = db_session.query(AuditLog).filter(AuditLog.request_id == request.id).count()
    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).count()
    assert events == 3
    assert runs == 1


def test_run_pipeline_handles_missing_request_without_raising(db_session: Session) -> None:
    processing_service.run_pipeline(db_session, uuid.uuid4())  # should not raise
