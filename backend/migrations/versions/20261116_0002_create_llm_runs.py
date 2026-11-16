"""create llm_runs table

Revision ID: 20261116_0002
Revises: 20261115_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261116_0002"
down_revision = "20261115_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("provider_code", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("repair_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('SUCCESS','PROVIDER_ERROR')", name="ck_llm_runs_status"),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0",
            name="ck_llm_runs_tokens_nonnegative",
        ),
    )
    op.create_index("ix_llm_runs_purpose_created", "llm_runs", ["purpose", sa.text("created_at DESC")])
    op.create_index("ix_llm_runs_inquiry_created", "llm_runs", ["inquiry_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("llm_runs")
