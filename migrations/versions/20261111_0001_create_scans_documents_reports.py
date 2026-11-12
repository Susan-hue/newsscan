"""create scans documents reports

Revision ID: 0001
Revises:
Create Date: 2026-11-11 22:05:41.463257
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_kind", sa.String(length=16), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_scans_status"), ["status"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("ocr_engine", sa.String(length=32), nullable=False),
        sa.Column("mean_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scans.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id"),
    )
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_documents_text_sha256"), ["text_sha256"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("band", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scans.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id"),
    )


def downgrade() -> None:
    op.drop_table("reports")
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_documents_text_sha256"))

    op.drop_table("documents")
    with op.batch_alter_table("scans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_scans_status"))

    op.drop_table("scans")
