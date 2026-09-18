"""Request CRUD, pagination/filtering/sorting, timeline, and tasks endpoints."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.request import ProcessingStatus, Request, RequestStatus
from app.models.user import User, UserRole
from app.models.workflow_task import WorkflowTask
from app.schemas.audit_log import AuditLogRead
from app.schemas.pagination import Page
from app.schemas.request import RequestCreate, RequestDetailRead, RequestRead, RequestUpdate
from app.schemas.workflow_task import WorkflowTaskRead
from app.services import audit_service, request_service
from app.workers.tasks import process_request as process_request_task

router = APIRouter(prefix="/api/requests", tags=["requests"])

# OPERATOR/ADMIN can see every request. Per-operator task assignment doesn't
# exist in the data model, so "view assigned requests" (spec) is approximated
# as "view all requests" for staff — same simplification as workflow_tasks.
STAFF_ROLES = (UserRole.OPERATOR, UserRole.ADMIN)


def _get_request_or_404(db: Session, request_id: uuid.UUID) -> Request:
    request = request_service.get_request(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def _enqueue_processing(request_id: uuid.UUID) -> None:
    """What actually keeps this from hanging for minutes when the broker is
    unreachable is the role-based broker_connection_max_retries in
    app/workers/celery_app.py, not anything here — see that file for the
    full story (it took several live-tested wrong turns to find, per Phase
    7's learning doc). Still a real, open gap even with that fix: if this
    call ultimately fails, the Request row already exists but was never
    (re-)queued, and nothing currently retries queueing it automatically
    later.
    """
    process_request_task.delay(str(request_id))


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
    request = request_service.create_request(
        db,
        requester=current_user,
        title=payload.title,
        description=payload.description,
        department=payload.department,
    )

    # Enqueue only after the transaction above has committed — otherwise a worker
    # could pick up the task and query for this request before the row is even
    # visible in the database (the API would return quickly, but the task would
    # immediately fail with "request not found").
    _enqueue_processing(request.id)

    return request


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


@router.get("/{request_id}", response_model=RequestDetailRead)
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


@router.post("/{request_id}/retry", response_model=RequestRead)
def retry_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN)),
) -> Request:
    request = _get_request_or_404(db, request_id)

    # Retryable when the pipeline itself technically failed (Phase 3/4), or
    # when it succeeded but the outcome needs another pass — a human fixed
    # something and wants the rule engine to re-evaluate (Phase 5), or the
    # request was stuck needing information that's since been clarified.
    retryable_statuses = (RequestStatus.MANUAL_REVIEW, RequestStatus.NEEDS_INFORMATION)
    if request.processing_status != ProcessingStatus.FAILED and request.status not in retryable_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only FAILED, MANUAL_REVIEW, or NEEDS_INFORMATION requests can be retried "
                f"(current status: {request.status.value}, processing_status: {request.processing_status.value})"
            ),
        )

    request.processing_status = ProcessingStatus.QUEUED
    db.flush()
    audit_service.record_event(
        db,
        request_id=request.id,
        event_type="PROCESSING_RETRIED",
        actor=_current_user.email,
        description=f"Reprocessing manually triggered by {_current_user.email}",
    )
    db.commit()
    db.refresh(request)

    _enqueue_processing(request.id)

    return request


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
