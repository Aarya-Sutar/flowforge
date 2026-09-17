"""Request CRUD, pagination/filtering/sorting, timeline, and tasks endpoints."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.request import Request, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_task import WorkflowTask
from app.schemas.audit_log import AuditLogRead
from app.schemas.pagination import Page
from app.schemas.request import RequestCreate, RequestRead, RequestUpdate
from app.schemas.workflow_task import WorkflowTaskRead
from app.services import request_service

router = APIRouter(prefix="/api/requests", tags=["requests"])

# OPERATOR/ADMIN can see every request. Task-based scoping for OPERATOR ("view assigned
# requests") is added in Phase 5 once workflow_tasks are actually populated with assignees.
STAFF_ROLES = (UserRole.OPERATOR, UserRole.ADMIN)


def _get_request_or_404(db: Session, request_id: uuid.UUID) -> Request:
    request = request_service.get_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def _ensure_can_view(request: Request, current_user: User) -> None:
    if current_user.role in STAFF_ROLES:
        return
    if request.requester_id != current_user.id:
        # 404, not 403: don't reveal that a request with this ID exists to someone
        # who isn't allowed to see it (avoids an insecure direct object reference leak).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")


@router.post("", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Request:
    return request_service.create_request(
        db,
        requester=current_user,
        title=payload.title,
        description=payload.description,
        department=payload.department,
    )


@router.get("", response_model=Page[RequestRead])
def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: RequestStatus | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    department: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: Literal["created_at", "updated_at", "priority", "status"] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> Page[RequestRead]:
    # A regular USER can only ever list their own requests — enforced server-side,
    # not by trusting a client-supplied filter.
    requester_id = None if current_user.role in STAFF_ROLES else current_user.id

    items, total = request_service.list_requests(
        db,
        requester_id=requester_id,
        status=status_filter,
        category=category,
        priority=priority,
        department=department,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=request_service.total_pages(total, page_size),
    )


@router.get("/{request_id}", response_model=RequestRead)
def get_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Request:
    request = _get_request_or_404(db, request_id)
    _ensure_can_view(request, current_user)
    return request


@router.patch("/{request_id}", response_model=RequestRead)
def update_request(
    request_id: uuid.UUID,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Request:
    request = _get_request_or_404(db, request_id)
    _ensure_can_view(request, current_user)

    is_staff = current_user.role in STAFF_ROLES

    if payload.status is not None and not is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operators or admins can change request status",
        )

    if not is_staff:
        if request.status != RequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Request can no longer be edited once processing has started",
            )
        if request.requester_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    return request_service.update_request(
        db,
        request=request,
        actor=current_user,
        title=payload.title,
        description=payload.description,
        department=payload.department,
        status=payload.status,
    )


@router.get("/{request_id}/timeline", response_model=list[AuditLogRead])
def get_request_timeline(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLog]:
    request = _get_request_or_404(db, request_id)
    _ensure_can_view(request, current_user)

    return list(
        db.execute(
            select(AuditLog).where(AuditLog.request_id == request_id).order_by(AuditLog.created_at.asc())
        ).scalars().all()
    )


@router.get("/{request_id}/tasks", response_model=list[WorkflowTaskRead])
def get_request_tasks(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowTask]:
    request = _get_request_or_404(db, request_id)
    _ensure_can_view(request, current_user)

    return list(
        db.execute(
            select(WorkflowTask)
            .where(WorkflowTask.request_id == request_id)
            .order_by(WorkflowTask.created_at.asc())
        ).scalars().all()
    )
