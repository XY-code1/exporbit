"""create immutable inquiry extraction records

Revision ID: 20261117_0004
Revises: 20261116_0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261117_0004"
down_revision = "20261116_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inquiry_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("llm_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider_code", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('SUCCESS','FAILED')", name="ck_inquiry_extractions_status"),
    )
    op.create_index("ix_inquiry_extractions_inquiry_created", "inquiry_extractions", ["inquiry_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("inquiry_extractions")
