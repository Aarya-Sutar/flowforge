from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.dashboard import DashboardMetrics, DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_STAFF_ROLES = (UserRole.OPERATOR, UserRole.ADMIN)


@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DashboardSummary:
    requester_id = None if current_user.role in _STAFF_ROLES else current_user.id
    return dashboard_service.get_summary(db, requester_id=requester_id)


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DashboardMetrics:
    requester_id = None if current_user.role in _STAFF_ROLES else current_user.id
    return dashboard_service.get_metrics(db, requester_id=requester_id)
