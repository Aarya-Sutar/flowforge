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
from app.models.request import ProcessingStatus, Request, RequestCategory, RequestPriority, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_rule import WorkflowRule
from app.models.workflow_task import WorkflowTask
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


def _seed_catch_all_rule(db_session: Session, team: str = "IT Team") -> None:
    """A rule that always matches (confidence is always >= 0 once CLASSIFY has
    run), so CLASSIFY-focused tests get a predictable ROUTE outcome (routed,
    task created) instead of falling into the rule engine's no-match fallback
    (MANUAL_REVIEW) — that fallback is tested directly in test_rules_engine.py."""
    db_session.add(WorkflowRule(name="Catch-all", condition="confidence >= 0.0", action=f"assign_team = {team}"))
    db_session.commit()


def test_normalize_text_collapses_whitespace() -> None:
    assert processing_service.normalize_text("  hello   world  \n\tfoo  ") == "hello world foo"


def test_run_pipeline_normalizes_description(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    db_session.refresh(request)
    assert request.normalized_description == "I cannot access the repo."


def test_run_pipeline_persists_ai_classification(db_session: Session) -> None:
    _seed_catch_all_rule(db_session)
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    db_session.refresh(request)
    assert request.category == RequestCategory.IT_SUPPORT
    assert request.subcategory == "ACCESS_REQUEST"
    assert request.priority == RequestPriority.HIGH
    assert request.confidence == 0.91
    assert request.summary == "Employee cannot access internal Git repository"
    assert request.processing_status == ProcessingStatus.COMPLETED
    # Routed successfully by the catch-all rule — PROCESSING means "handed off
    # to a team," not "the underlying issue is resolved" (see Phase 5 docs).
    assert request.status == RequestStatus.PROCESSING


def test_run_pipeline_persists_extracted_entities(db_session: Session) -> None:
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    entities = {e.key: e.value for e in db_session.query(ExtractedEntity).filter(ExtractedEntity.request_id == request.id)}
    assert entities == {"system": "git repository", "issue": "access denied"}


def test_run_pipeline_creates_three_processing_runs(db_session: Session) -> None:
    _seed_catch_all_rule(db_session)
    request = _make_request(db_session)
    processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).order_by(ProcessingRun.started_at).all()
    assert [r.stage for r in runs] == ["NORMALIZE", "CLASSIFY", "ROUTE"]
    assert all(r.status == ProcessingRunStatus.SUCCEEDED for r in runs)


def test_run_pipeline_writes_expected_audit_events(db_session: Session) -> None:
    _seed_catch_all_rule(db_session)
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
        "RULE_EVALUATION_COMPLETED",
        "RULE_TRIGGERED",
        "REQUEST_ROUTED",
        "TASK_CREATED",
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
    _seed_catch_all_rule(db_session)
    request = _make_request(db_session)
    provider = StubProvider(_stub_result())

    processing_service.run_pipeline(db_session, request.id, ai_provider=provider)
    processing_service.run_pipeline(db_session, request.id, ai_provider=provider)  # simulates Celery redelivery

    runs = db_session.query(ProcessingRun).filter(ProcessingRun.request_id == request.id).count()
    assert runs == 3
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


class TestRouteStage:
    """Integration tests for the ROUTE stage specifically — the rule engine
    itself is unit-tested in test_rules_engine.py; these confirm it's wired
    into the pipeline correctly end-to-end (task creation, request state)."""

    def test_successful_routing_creates_a_workflow_task(self, db_session: Session) -> None:
        db_session.add(WorkflowRule(
            name="Access routing", category="ACCESS_REQUEST",
            condition="category == ACCESS_REQUEST AND confidence >= 0.80",
            action="assign_team = IT Security Team",
        ))
        db_session.commit()
        request = _make_request(db_session)

        processing_service.run_pipeline(
            db_session, request.id,
            ai_provider=StubProvider(_stub_result(category=RequestCategory.ACCESS_REQUEST, confidence=0.9)),
        )

        db_session.refresh(request)
        assert request.status == RequestStatus.PROCESSING
        assert request.assigned_team == "IT Security Team"

        tasks = db_session.query(WorkflowTask).filter(WorkflowTask.request_id == request.id).all()
        assert len(tasks) == 1
        assert tasks[0].task_type == "ACCESS_REVIEW_TASK"
        assert tasks[0].assigned_team == "IT Security Team"

    def test_low_confidence_routes_to_manual_review_without_creating_task(self, db_session: Session) -> None:
        db_session.add(WorkflowRule(name="Low confidence", condition="confidence < 0.70", action="status = MANUAL_REVIEW"))
        db_session.commit()
        request = _make_request(db_session)

        processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result(confidence=0.4)))

        db_session.refresh(request)
        assert request.status == RequestStatus.MANUAL_REVIEW
        assert request.assigned_team is None
        assert db_session.query(WorkflowTask).filter(WorkflowTask.request_id == request.id).count() == 0

    def test_missing_finance_amount_routes_to_needs_information(self, db_session: Session) -> None:
        db_session.add(WorkflowRule(
            name="Missing amount", category="FINANCE", condition="amount IS NULL", action="status = NEEDS_INFORMATION",
        ))
        db_session.commit()
        request = _make_request(db_session)

        processing_service.run_pipeline(
            db_session, request.id,
            ai_provider=StubProvider(_stub_result(category=RequestCategory.FINANCE, amount=None)),
        )

        db_session.refresh(request)
        assert request.status == RequestStatus.NEEDS_INFORMATION

    def test_finance_over_threshold_creates_approval_task(self, db_session: Session) -> None:
        db_session.add(WorkflowRule(name="Finance routing", category="FINANCE", condition="category == FINANCE", action="assign_team = Finance Team"))
        db_session.add(WorkflowRule(
            name="Finance approval threshold", category="FINANCE",
            condition="category == FINANCE AND amount > 100000", action="require_approval = true",
        ))
        db_session.commit()
        request = _make_request(db_session)

        processing_service.run_pipeline(
            db_session, request.id,
            ai_provider=StubProvider(_stub_result(category=RequestCategory.FINANCE, amount=150000.0)),
        )

        tasks = db_session.query(WorkflowTask).filter(WorkflowTask.request_id == request.id).all()
        assert len(tasks) == 1
        assert tasks[0].task_type == "APPROVAL_TASK"

    def test_no_matching_rule_falls_back_to_manual_review(self, db_session: Session) -> None:
        # No workflow_rules seeded at all in this test's db_session.
        request = _make_request(db_session)

        processing_service.run_pipeline(db_session, request.id, ai_provider=StubProvider(_stub_result()))

        db_session.refresh(request)
        assert request.status == RequestStatus.MANUAL_REVIEW
        assert request.assigned_team is None

    def test_mark_urgent_action_sets_task_priority_high(self, db_session: Session) -> None:
        db_session.add(WorkflowRule(name="Routing", condition="confidence >= 0.0", action="assign_team = IT Team"))
        db_session.add(WorkflowRule(name="Urgent", condition="priority == HIGH", action="mark_urgent = true"))
        db_session.commit()
        request = _make_request(db_session)

        processing_service.run_pipeline(
            db_session, request.id,
            ai_provider=StubProvider(_stub_result(priority=RequestPriority.HIGH)),
        )

        task = db_session.query(WorkflowTask).filter(WorkflowTask.request_id == request.id).one()
        assert task.priority == RequestPriority.HIGH


def test_run_pipeline_skips_when_lock_is_already_held(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves the wiring, not just the lock in isolation (see
    test_locking.py): if another worker already holds this request's lock,
    run_pipeline must do nothing rather than process concurrently."""
    import fakeredis

    from app.services import locking

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(locking, "redis_client", fake)

    request = _make_request(db_session)
    fake.set(f"flowforge:pipeline-lock:{request.id}", "1")  # simulate a concurrent worker

    provider = StubProvider(_stub_result())
    processing_service.run_pipeline(db_session, request.id, ai_provider=provider)

    db_session.refresh(request)
    assert request.processing_status == ProcessingStatus.QUEUED  # untouched
    assert provider.calls == 0
