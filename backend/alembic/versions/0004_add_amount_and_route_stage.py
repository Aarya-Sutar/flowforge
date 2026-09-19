"""add requests.amount

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18

"""
from typing import Union
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("amount", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("requests", "amount")
