"""CRUD for admin-configured workflow rules. Evaluation logic lands in Phase 5."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow_rule import WorkflowRule


def create_rule(
    db: Session,
    *,
    name: str,
    description: str | None,
    category: str | None,
    condition: str,
    action: str,
    enabled: bool,
) -> WorkflowRule:
    rule = WorkflowRule(
        name=name,
        description=description,
        category=category,
        condition=condition,
        action=action,
        enabled=enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session) -> list[WorkflowRule]:
    return list(db.execute(select(WorkflowRule).order_by(WorkflowRule.created_at.desc())).scalars().all())


def get_rule(db: Session, rule_id: uuid.UUID) -> WorkflowRule | None:
    return db.get(WorkflowRule, rule_id)


def update_rule(
    db: Session,
    *,
    rule: WorkflowRule,
    name: str | None,
    description: str | None,
    category: str | None,
    condition: str | None,
    action: str | None,
    enabled: bool | None,
) -> WorkflowRule:
    if name is not None:
        rule.name = name
    if description is not None:
        rule.description = description
    if category is not None:
        rule.category = category
    if condition is not None:
        rule.condition = condition
    if action is not None:
        rule.action = action
    if enabled is not None:
        rule.enabled = enabled

    db.commit()
    db.refresh(rule)
    return rule
