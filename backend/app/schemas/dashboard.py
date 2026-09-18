from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total: int
    pending: int
    processing: int
    needs_information: int
    manual_review: int
    completed: int
    failed: int
    # None when no request has finished processing yet — there's nothing to
    # average. Computed from requests.updated_at - requests.created_at for
    # requests whose processing_status is COMPLETED; a reasonable
    # approximation, not a precise per-stage timer (see Phase 6 docs).
    average_processing_time_seconds: float | None


class CategoryCount(BaseModel):
    category: str | None
    count: int


class StatusCount(BaseModel):
    status: str
    count: int


class PriorityCount(BaseModel):
    priority: str | None
    count: int


class DailyCount(BaseModel):
    date: str
    count: int


class DashboardMetrics(BaseModel):
    requests_by_category: list[CategoryCount]
    requests_by_status: list[StatusCount]
    priority_distribution: list[PriorityCount]
    processing_succeeded: int
    processing_failed: int
    requests_over_time: list[DailyCount]
