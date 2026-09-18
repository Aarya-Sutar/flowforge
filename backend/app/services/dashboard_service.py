"""Real aggregate queries backing the dashboard — every number here comes
from an actual SQL aggregate over the requests table, never a hardcoded
placeholder. Scoped to the caller's own requests for a regular USER, global
for OPERATOR/ADMIN — the same visibility rule Phase 2 established for
GET /api/requests.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.request import ProcessingStatus, Request, RequestStatus
from app.schemas.dashboard import (
    CategoryCount,
    DailyCount,
    DashboardMetrics,
    DashboardSummary,
    PriorityCount,
    StatusCount,
)

_HISTORY_DAYS = 14


def _scope(query, requester_id: uuid.UUID | None):
    return query.where(Request.requester_id == requester_id) if requester_id is not None else query


def get_summary(db: Session, *, requester_id: uuid.UUID | None) -> DashboardSummary:
    status_counts = dict(
        db.execute(
            _scope(select(Request.status, func.count()).group_by(Request.status), requester_id)
        ).all()
    )
    total = sum(status_counts.values())

    # Computed in Python rather than with a SQL EXTRACT(EPOCH FROM ...) —
    # that function is Postgres-specific and doesn't translate to SQLite,
    # which the test suite runs against (see Phase 1 docs on that trade-off).
    completed_timestamps = db.execute(
        _scope(
            select(Request.created_at, Request.updated_at)
            .where(Request.processing_status == ProcessingStatus.COMPLETED),
            requester_id,
        )
    ).all()
    durations = [(updated - created).total_seconds() for created, updated in completed_timestamps]
    avg_seconds = sum(durations) / len(durations) if durations else None

    return DashboardSummary(
        total=total,
        pending=status_counts.get(RequestStatus.PENDING, 0),
        processing=status_counts.get(RequestStatus.PROCESSING, 0),
        needs_information=status_counts.get(RequestStatus.NEEDS_INFORMATION, 0),
        manual_review=status_counts.get(RequestStatus.MANUAL_REVIEW, 0),
        completed=status_counts.get(RequestStatus.COMPLETED, 0),
        failed=status_counts.get(RequestStatus.FAILED, 0),
        average_processing_time_seconds=avg_seconds,
    )


def get_metrics(db: Session, *, requester_id: uuid.UUID | None) -> DashboardMetrics:
    category_rows = db.execute(
        _scope(select(Request.category, func.count()).group_by(Request.category), requester_id)
    ).all()
    status_rows = db.execute(
        _scope(select(Request.status, func.count()).group_by(Request.status), requester_id)
    ).all()
    priority_rows = db.execute(
        _scope(select(Request.priority, func.count()).group_by(Request.priority), requester_id)
    ).all()
    succeeded = db.execute(
        _scope(
            select(func.count()).where(Request.processing_status == ProcessingStatus.COMPLETED), requester_id
        )
    ).scalar_one()
    failed = db.execute(
        _scope(select(func.count()).where(Request.processing_status == ProcessingStatus.FAILED), requester_id)
    ).scalar_one()

    since = datetime.now(timezone.utc) - timedelta(days=_HISTORY_DAYS)
    daily_rows = db.execute(
        _scope(
            select(func.date(Request.created_at), func.count())
            .where(Request.created_at >= since)
            .group_by(func.date(Request.created_at))
            .order_by(func.date(Request.created_at)),
            requester_id,
        )
    ).all()

    return DashboardMetrics(
        requests_by_category=[
            CategoryCount(category=cat.value if cat else None, count=count) for cat, count in category_rows
        ],
        requests_by_status=[StatusCount(status=status.value, count=count) for status, count in status_rows],
        priority_distribution=[
            PriorityCount(priority=p.value if p else None, count=count) for p, count in priority_rows
        ],
        processing_succeeded=succeeded,
        processing_failed=failed,
        requests_over_time=[DailyCount(date=str(day), count=count) for day, count in daily_rows],
    )
