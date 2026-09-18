"""The deterministic rule engine. Runs AFTER AI classification, decides
routing, and is the only thing allowed to make that decision — this is
FLOWFORGE_SPEC.md's central rule: "The LLM must NOT be allowed to directly
execute arbitrary actions." The AI's output is one input among several
(confidence, amount, department) this engine evaluates against
admin-configured, database-stored rules.
"""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.request import Request, RequestStatus
from app.models.workflow_rule import WorkflowRule
from app.rules.actions import parse_action
from app.rules.condition import evaluate_condition
from app.rules.exceptions import RuleParseError

# Terminal outcomes always override team routing, regardless of what else
# triggered. Between the two, NEEDS_INFORMATION wins: if required data is
# missing, nothing else evaluated against that data can be trusted either.
_TERMINAL_STATUS_PRECEDENCE = [RequestStatus.NEEDS_INFORMATION, RequestStatus.MANUAL_REVIEW]


@dataclass
class RuleEvaluation:
    rule_id: str
    rule_name: str
    condition: str
    triggered: bool
    action: str | None = None
    error: str | None = None


@dataclass
class RuleEngineResult:
    evaluations: list[RuleEvaluation] = field(default_factory=list)
    terminal_status: RequestStatus | None = None
    assigned_team: str | None = None
    require_approval: bool = False
    mark_urgent: bool = False

    @property
    def triggered_evaluations(self) -> list[RuleEvaluation]:
        return [e for e in self.evaluations if e.triggered and e.error is None]


def _build_context(request: Request) -> dict[str, object]:
    return {
        "category": request.category,
        "subcategory": request.subcategory,
        "priority": request.priority,
        "confidence": request.confidence,
        "department": request.department,
        "amount": request.amount,
    }


def evaluate_rules(db: Session, request: Request) -> RuleEngineResult:
    rules = list(
        db.execute(
            select(WorkflowRule)
            .where(WorkflowRule.enabled.is_(True))
            .where(
                (WorkflowRule.category.is_(None))
                | (WorkflowRule.category == (request.category.value if request.category else None))
            )
            .order_by(WorkflowRule.created_at.asc())
        ).scalars().all()
    )

    context = _build_context(request)
    result = RuleEngineResult()
    triggered_status_actions: dict[RequestStatus, bool] = {}

    for rule in rules:
        try:
            triggered = evaluate_condition(rule.condition, context)
        except RuleParseError as exc:
            result.evaluations.append(
                RuleEvaluation(
                    rule_id=str(rule.id), rule_name=rule.name, condition=rule.condition,
                    triggered=False, error=f"condition error: {exc}",
                )
            )
            continue

        if not triggered:
            result.evaluations.append(
                RuleEvaluation(rule_id=str(rule.id), rule_name=rule.name, condition=rule.condition, triggered=False)
            )
            continue

        try:
            key, value = parse_action(rule.action)
        except RuleParseError as exc:
            result.evaluations.append(
                RuleEvaluation(
                    rule_id=str(rule.id), rule_name=rule.name, condition=rule.condition,
                    triggered=True, error=f"action error: {exc}",
                )
            )
            continue

        result.evaluations.append(
            RuleEvaluation(
                rule_id=str(rule.id), rule_name=rule.name, condition=rule.condition,
                triggered=True, action=rule.action,
            )
        )

        if key == "status":
            try:
                triggered_status_actions[RequestStatus(value)] = True
            except ValueError:
                result.evaluations[-1].error = f"action error: unknown status {value!r}"
        elif key == "assign_team":
            result.assigned_team = value  # last-triggered-rule-wins for this key
        elif key == "require_approval":
            result.require_approval = result.require_approval or value.lower() == "true"
        elif key == "mark_urgent":
            result.mark_urgent = result.mark_urgent or value.lower() == "true"

    for status in _TERMINAL_STATUS_PRECEDENCE:
        if triggered_status_actions.get(status):
            result.terminal_status = status
            break

    return result
