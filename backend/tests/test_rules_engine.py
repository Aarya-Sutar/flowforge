"""Tests the rule engine directly against a Session — creates real
WorkflowRule rows and a real Request, then checks the routing decision.
Mirrors every example rule in FLOWFORGE_SPEC.md's business rule engine
section, plus the conflict-resolution policy documented in
docs/learning/PHASE_5_BUSINESS_AUTOMATION.md.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.request import ProcessingStatus, Request, RequestCategory, RequestPriority, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_rule import WorkflowRule
from app.rules.engine import evaluate_rules


def _make_request(db_session: Session, **overrides) -> Request:
    user = User(name="Requester", email=f"{uuid.uuid4()}@example.com", password_hash=hash_password("password123"), role=UserRole.USER)
    db_session.add(user)
    db_session.commit()

    defaults = dict(
        requester_id=user.id,
        title="Test request",
        description="Test description",
        department="Engineering",
        status=RequestStatus.PENDING,
        processing_status=ProcessingStatus.IN_PROGRESS,
        category=RequestCategory.ACCESS_REQUEST,
        priority=RequestPriority.MEDIUM,
        confidence=0.9,
    )
    defaults.update(overrides)
    request = Request(**defaults)
    db_session.add(request)
    db_session.commit()
    db_session.refresh(request)
    return request


def _make_rule(db_session: Session, *, name, condition, action, category=None, enabled=True) -> WorkflowRule:
    rule = WorkflowRule(name=name, condition=condition, action=action, category=category, enabled=enabled)
    db_session.add(rule)
    db_session.commit()
    return rule


def test_access_request_high_confidence_routes_to_security_team(db_session: Session) -> None:
    _make_rule(
        db_session, name="Access routing", category="ACCESS_REQUEST",
        condition="category == ACCESS_REQUEST AND confidence >= 0.80",
        action="assign_team = IT Security Team",
    )
    request = _make_request(db_session, category=RequestCategory.ACCESS_REQUEST, confidence=0.9)

    result = evaluate_rules(db_session, request)

    assert result.assigned_team == "IT Security Team"
    assert result.terminal_status is None


def test_low_confidence_routes_to_manual_review(db_session: Session) -> None:
    _make_rule(
        db_session, name="Low confidence review", condition="confidence < 0.70", action="status = MANUAL_REVIEW"
    )
    request = _make_request(db_session, confidence=0.4)

    result = evaluate_rules(db_session, request)

    assert result.terminal_status == RequestStatus.MANUAL_REVIEW


def test_high_priority_marks_urgent(db_session: Session) -> None:
    _make_rule(db_session, name="Urgent escalation", condition="priority == HIGH", action="mark_urgent = true")
    request = _make_request(db_session, priority=RequestPriority.HIGH)

    result = evaluate_rules(db_session, request)

    assert result.mark_urgent is True


def test_missing_amount_routes_to_needs_information(db_session: Session) -> None:
    _make_rule(
        db_session, name="Missing amount", category="FINANCE",
        condition="amount IS NULL", action="status = NEEDS_INFORMATION",
    )
    request = _make_request(db_session, category=RequestCategory.FINANCE, amount=None)

    result = evaluate_rules(db_session, request)

    assert result.terminal_status == RequestStatus.NEEDS_INFORMATION


def test_needs_information_outranks_manual_review_when_both_trigger(db_session: Session) -> None:
    _make_rule(
        db_session, name="Low confidence review", condition="confidence < 0.70", action="status = MANUAL_REVIEW"
    )
    _make_rule(
        db_session, name="Missing amount", category="FINANCE",
        condition="amount IS NULL", action="status = NEEDS_INFORMATION",
    )
    request = _make_request(db_session, category=RequestCategory.FINANCE, confidence=0.4, amount=None)

    result = evaluate_rules(db_session, request)

    assert result.terminal_status == RequestStatus.NEEDS_INFORMATION


def test_finance_amount_over_threshold_requires_approval(db_session: Session) -> None:
    _make_rule(
        db_session, name="Finance default routing", category="FINANCE",
        condition="category == FINANCE", action="assign_team = Finance Team",
    )
    _make_rule(
        db_session, name="Finance approval threshold", category="FINANCE",
        condition="category == FINANCE AND amount > 100000", action="require_approval = true",
    )
    request = _make_request(db_session, category=RequestCategory.FINANCE, amount=150000.0)

    result = evaluate_rules(db_session, request)

    assert result.assigned_team == "Finance Team"
    assert result.require_approval is True


def test_disabled_rule_never_triggers(db_session: Session) -> None:
    _make_rule(
        db_session, name="Disabled rule", condition="confidence < 0.70", action="status = MANUAL_REVIEW",
        enabled=False,
    )
    request = _make_request(db_session, confidence=0.4)

    result = evaluate_rules(db_session, request)

    assert result.terminal_status is None
    assert all(not e.triggered for e in result.evaluations)


def test_no_matching_rule_leaves_assigned_team_none(db_session: Session) -> None:
    _make_rule(
        db_session, name="HR only", category="HR",
        condition="category == HR", action="assign_team = HR Team",
    )
    request = _make_request(db_session, category=RequestCategory.ACCESS_REQUEST)

    result = evaluate_rules(db_session, request)

    assert result.assigned_team is None
    assert result.terminal_status is None


def test_malformed_rule_is_skipped_not_crashed(db_session: Session) -> None:
    _make_rule(db_session, name="Broken rule", condition="not_a_field == X", action="assign_team = Somewhere")
    _make_rule(db_session, name="Good rule", condition="category == ACCESS_REQUEST", action="assign_team = IT Security Team")
    request = _make_request(db_session, category=RequestCategory.ACCESS_REQUEST)

    result = evaluate_rules(db_session, request)

    assert result.assigned_team == "IT Security Team"
    broken = next(e for e in result.evaluations if e.rule_name == "Broken rule")
    assert broken.error is not None


def test_later_rule_wins_for_same_action_key(db_session: Session) -> None:
    _make_rule(db_session, name="First", condition="category == ACCESS_REQUEST", action="assign_team = Team A")
    _make_rule(db_session, name="Second", condition="category == ACCESS_REQUEST", action="assign_team = Team B")
    request = _make_request(db_session, category=RequestCategory.ACCESS_REQUEST)

    result = evaluate_rules(db_session, request)

    assert result.assigned_team == "Team B"


def test_universal_rule_with_no_category_applies_to_every_category(db_session: Session) -> None:
    _make_rule(db_session, name="Global low confidence", category=None, condition="confidence < 0.70", action="status = MANUAL_REVIEW")
    request = _make_request(db_session, category=RequestCategory.HR, confidence=0.3)

    result = evaluate_rules(db_session, request)

    assert result.terminal_status == RequestStatus.MANUAL_REVIEW
