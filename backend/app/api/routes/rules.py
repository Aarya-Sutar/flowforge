"""Admin-only CRUD for workflow rules."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.workflow_rule import WorkflowRule
from app.schemas.rule import RuleCreate, RuleRead, RuleUpdate
from app.services import rule_service

router = APIRouter(prefix="/api/rules", tags=["rules"])

admin_only = require_roles(UserRole.ADMIN)


@router.get("", response_model=list[RuleRead])
def list_rules(
    db: Session = Depends(get_db),
    _current_user: User = Depends(admin_only),
) -> list[WorkflowRule]:
    return rule_service.list_rules(db)


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(admin_only),
) -> WorkflowRule:
    return rule_service.create_rule(
        db,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        condition=payload.condition,
        action=payload.action,
        enabled=payload.enabled,
    )


@router.patch("/{rule_id}", response_model=RuleRead)
def update_rule(
    rule_id: uuid.UUID,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(admin_only),
) -> WorkflowRule:
    rule = rule_service.get_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    return rule_service.update_rule(
        db,
        rule=rule,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        condition=payload.condition,
        action=payload.action,
        enabled=payload.enabled,
    )
