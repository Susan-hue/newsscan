"""add scans.file_deleted_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("file_deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.drop_column("file_deleted_at")
