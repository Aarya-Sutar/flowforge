"""create requests, extracted_entities, workflow_tasks, workflow_rules, audit_logs, processing_runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

request_status = postgresql.ENUM(
    "PENDING", "PROCESSING", "NEEDS_INFORMATION", "MANUAL_REVIEW", "COMPLETED", "FAILED",
    name="request_status",
)
processing_status = postgresql.ENUM(
    "QUEUED", "IN_PROGRESS", "COMPLETED", "FAILED", name="processing_status"
)
request_category = postgresql.ENUM(
    "IT_SUPPORT", "HR", "FINANCE", "PROCUREMENT", "CUSTOMER_SERVICE", "ACCESS_REQUEST", "GENERAL",
    name="request_category",
)
request_priority = postgresql.ENUM("LOW", "MEDIUM", "HIGH", "URGENT", name="request_priority")
task_status = postgresql.ENUM("OPEN", "IN_PROGRESS", "DONE", name="task_status")
processing_run_status = postgresql.ENUM("STARTED", "SUCCEEDED", "FAILED", name="processing_run_status")


def upgrade() -> None:
    bind = op.get_bind()
    request_status.create(bind, checkfirst=True)
    processing_status.create(bind, checkfirst=True)
    request_category.create(bind, checkfirst=True)
    request_priority.create(bind, checkfirst=True)
    task_status.create(bind, checkfirst=True)
    processing_run_status.create(bind, checkfirst=True)

    op.create_table(
        "requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "PROCESSING", "NEEDS_INFORMATION", "MANUAL_REVIEW", "COMPLETED", "FAILED",
                name="request_status", create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "processing_status",
            postgresql.ENUM("QUEUED", "IN_PROGRESS", "COMPLETED", "FAILED", name="processing_status", create_type=False),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column(
            "category",
            postgresql.ENUM(
                "IT_SUPPORT", "HR", "FINANCE", "PROCUREMENT", "CUSTOMER_SERVICE", "ACCESS_REQUEST", "GENERAL",
                name="request_category", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("subcategory", sa.String(length=100), nullable=True),
        sa.Column(
            "priority",
            postgresql.ENUM("LOW", "MEDIUM", "HIGH", "URGENT", name="request_priority", create_type=False),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("assigned_team", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_requests_requester_id", "requests", ["requester_id"])
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_category", "requests", ["category"])
    op.create_index("ix_requests_created_at", "requests", ["created_at"])

    op.create_table(
        "extracted_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_extracted_entities_request_id", "extracted_entities", ["request_id"])

    op.create_table(
        "workflow_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("assigned_team", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("OPEN", "IN_PROGRESS", "DONE", name="task_status", create_type=False),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column(
            "priority",
            postgresql.ENUM("LOW", "MEDIUM", "HIGH", "URGENT", name="request_priority", create_type=False),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_tasks_request_id", "workflow_tasks", ["request_id"])

    op.create_table(
        "workflow_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_rules_category", "workflow_rules", ["category"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])

    op.create_table(
        "processing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("stage", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("STARTED", "SUCCEEDED", "FAILED", name="processing_run_status", create_type=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_processing_runs_request_id", "processing_runs", ["request_id"])


def downgrade() -> None:
    op.drop_table("processing_runs")
    op.drop_table("audit_logs")
    op.drop_table("workflow_rules")
    op.drop_table("workflow_tasks")
    op.drop_table("extracted_entities")
    op.drop_table("requests")

    bind = op.get_bind()
    processing_run_status.drop(bind, checkfirst=True)
    task_status.drop(bind, checkfirst=True)
    request_priority.drop(bind, checkfirst=True)
    request_category.drop(bind, checkfirst=True)
    processing_status.drop(bind, checkfirst=True)
    request_status.drop(bind, checkfirst=True)
