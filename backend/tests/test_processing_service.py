"""Tests the pipeline logic directly against a Session — no Celery, no broker,
no HTTP. This is exactly why app/services/processing_service.py is a separate,
plain function from app/workers/tasks.py's Celery-bound wrapper."""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderError
from app.ai.schemas import AIClassificationResult
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.extracted_entity import ExtractedEntity
from app.models.processing_run import ProcessingRun, ProcessingRunStatus
from app.models.request import ProcessingStatus, Request, RequestPriority, RequestStatus, RequestCategory
from app.models.user import User, UserRole
from app.services import processing_service


class StubProvider(AIProvider):
    """Deterministic test double — no keyword logic, just returns a fixed result."""

    def __init__(self, result: AIClassificationResult | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.calls = 0

    def classify(self, title: str, description: str) -> AIClassificationResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result


def _stub_result(**overrides) -> AIClassificationResult:
    defaults = dict(
        category=RequestCategory.IT_SUPPORT,
        subcategory="ACCESS_REQUEST",
        priority=RequestPriority.HIGH,
        summary="Employee cannot access internal Git repository",
        entities={"system": "git repository", "issue": "access denied"},
        confidence=0.91,
    )
    defaults.update(overrides)
    return AIClassificationResult(**defaults)


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
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    db_session.refresh(request)
    assert request.normalized_description == "I cannot access the repo."


def test_run_pipeline_persists_ai_classification(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    db_session.refresh(request)
    assert request.category == RequestCategory.IT_SUPPORT
    assert request.subcategory == "ACCESS_REQUEST"
    assert request.priority == RequestPriority.HIGH
    assert request.confidence == 0.91
    assert request.summary == "Employee cannot access internal Git repository"
    assert request.processing_status == ProcessingStatus.COMPLETED
    # Phase 5 (business rules/routing) hasn't run — business status must not
    # silently advance just because classification succeeded.
    assert request.status == RequestStatus.PENDING


def test_run_pipeline_persists_extracted_entities(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    entities = {e.key: e.value for e in db_session.query(ExtractedEntity).filter(ExtractedEntity.request_id == request.id)}
    assert entities == {"system": "git repository", "issue": "access denied"}


def test_run_pipeline_creates_two_processing_runs(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).order_by(ProcessingRun.started_at).all()
    assert [r.stage for r in runs] == ["NORMALIZE", "CLASSIFY"]
    assert all(r.status == ProcessingRunStatus.SUCCEEDED for r in runs)


def test_run_pipeline_writes_expected_audit_events(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    events = [
        log.event_type
        for log in db_session.query(AuditLog).filter(AuditLog.request_id == request.id).order_by(AuditLog.created_at)
    ]
    assert events == [
        "PROCESSING_STARTED",
        "TEXT_NORMALIZED",
        "AI_CLASSIFICATION_COMPLETED",
        "INFORMATION_EXTRACTED",
        "VALIDATION_COMPLETED",
        "PROCESSING_COMPLETED",
    ]


def test_run_pipeline_skips_information_extracted_when_no_entities(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result(entities={})))

    events = [
        log.event_type
        for log in db_session.query(AuditLog).filter(AuditLog.request_id == request.id)
    ]
    assert "INFORMATION_EXTRACTED" not in events


def test_run_pipeline_is_idempotent(db_session: Session) -> None:
    request = _make_request(db_session)
    provider = StubProvider(_stub_result())

    processing_service.run_pipeline(db_session, request.id, ai_provider=provider)
    processing_service.run_pipeline(db_session, request.id, ai_provider=provider)  # simulates Celery redelivery

    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).count()
    assert runs == 2
    assert provider.calls == 1  # second run never even called the provider


def test_run_pipeline_handles_missing_request_without_raising(db_session: Session) -> None:
    processing_service.run_pipeline(db_session, uuid.uuid4(), ai_provider=StubProvider(_stub_result()))


def test_run_pipeline_marks_failed_on_ai_provider_error(db_session: Session) -> None:
    request = _make_request(db_session)
    provider = StubProvider(error=AIProviderError("timeout"))

    with pytest.raises(AIProviderError):
        processing_service.run_pipeline(db_session, request.id, ai_provider=provider)

    db_session.refresh(request)
    assert request.processing_status == ProcessingStatus.FAILED
    assert request.category is None  # never got persisted

    events = [
        log.event_type
        for log in db_session.query(AuditLog).filter(AuditLog.request_id == request.id)
    ]
    assert "PROCESSING_FAILED" in events


def test_mark_manual_review_sets_status_and_audit_log(db_session: Session) -> None:
    request = _make_request(db_session)

    processing_service.mark_manual_review(db_session, request.id, reason="AI provider unreachable after 3 attempts")

    db_session.refresh(request)
    assert request.status == RequestStatus.MANUAL_REVIEW

    events = [
        log.event_type
        for log in db_session.query(AuditLog).filter(AuditLog.request_id == request.id)
    ]
    assert "MANUAL_REVIEW_REQUIRED" in events
