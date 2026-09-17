"""Business logic for creating, listing, retrieving, and updating requests."""
import math
import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.request import ProcessingStatus, Request, RequestStatus
from app.models.user import User
from app.services import audit_service

SORTABLE_FIELDS = {
    "created_at": Request.created_at,
    "updated_at": Request.updated_at,
    "priority": Request.priority,
    "status": Request.status,
}


def create_request(db: Session, *, requester: User, title: str, description: str, department: str) -> Request:
    request = Request(
        requester_id=requester.id,
        title=title,
        description=description,
        department=department,
        status=RequestStatus.PENDING,
        processing_status=ProcessingStatus.QUEUED,
    )
    db.add(request)
    db.flush()

    audit_service.record_event(
        db,
        request_id=request.id,
        event_type="REQUEST_CREATED",
        actor=requester.email,
        description=f'Request "{title}" created by {requester.email}',
    )

    db.commit()
    db.refresh(request)
    return request


def get_request(db: Session, request_id: uuid.UUID) -> Request | None:
    return db.get(Request, request_id)


def list_requests(
    db: Session,
    *,
    requester_id: uuid.UUID | None,
    status: RequestStatus | None,
    category: str | None,
    priority: str | None,
    department: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[Request], int]:
    query: Select = select(Request)

    if requester_id is not None:
        query = query.where(Request.requester_id == requester_id)
    if status is not None:
        query = query.where(Request.status == status)
    if category is not None:
        query = query.where(Request.category == category)
    if priority is not None:
        query = query.where(Request.priority == priority)
    if department is not None:
        query = query.where(Request.department.ilike(f"%{department}%"))

    # COUNT via a subquery rather than fetching every row into memory just to len() it —
    # this is the difference between an O(1)-network-trip count and an O(n) data transfer.
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()

    sort_column = SORTABLE_FIELDS.get(sort_by, Request.created_at)
    sort_column = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    query = query.order_by(sort_column).offset((page - 1) * page_size).limit(page_size)

    items = list(db.execute(query).scalars().all())
    return items, total


def update_request(
    db: Session,
    *,
    request: Request,
    actor: User,
    title: str | None,
    description: str | None,
    department: str | None,
    status: RequestStatus | None,
) -> Request:
    changes = []
    if title is not None and title != request.title:
        request.title = title
        changes.append("title")
    if description is not None and description != request.description:
        request.description = description
        changes.append("description")
    if department is not None and department != request.department:
        request.department = department
        changes.append("department")
    if status is not None and status != request.status:
        request.status = status
        changes.append("status")

    if changes:
        db.flush()
        audit_service.record_event(
            db,
            request_id=request.id,
            event_type="REQUEST_UPDATED",
            actor=actor.email,
            description=f"Fields updated: {', '.join(changes)}",
            metadata={"fields": changes},
        )
        db.commit()
        db.refresh(request)

    return request


def total_pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))
