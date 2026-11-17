"""create evidence provenance tables

Revision ID: 20261116_0003
Revises: 20261116_0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261116_0003"
down_revision = "20261116_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_health_status", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("mode IN ('LIVE','MANUAL','DEMO','PLANNED')", name="ck_source_providers_mode"),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('CUSTOMER_INQUIRY','ENTERPRISE','ZHIHU','OFFICIAL','OVERSEAS')",
            name="ck_source_providers_category",
        ),
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_category", sa.String(32), nullable=False),
        sa.Column("provider_mode", sa.String(16), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("canonical_url", sa.String(500), nullable=True),
        sa.Column("captured_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("availability_status", sa.String(16), nullable=False, server_default="AVAILABLE"),
        sa.Column("credibility_status", sa.String(32), nullable=False, server_default="NEEDS_CONFIRMATION"),
        sa.Column("captured_by", sa.String(80), nullable=True),
        sa.Column("usage_note", sa.String(500), nullable=True),
        sa.CheckConstraint("availability_status IN ('AVAILABLE','UNAVAILABLE')", name="ck_evidence_availability"),
        sa.CheckConstraint(
            "credibility_status IN ('CONFIRMED','INFERRED','NEEDS_CONFIRMATION','INSUFFICIENT_DATA','UNAVAILABLE')",
            name="ck_evidence_credibility",
        ),
        sa.CheckConstraint("is_demo = (provider_mode = 'DEMO')", name="ck_evidence_demo_flag_matches_mode"),
        sa.CheckConstraint("length(trim(captured_text)) > 0", name="ck_evidence_snapshot_not_empty"),
    )
    op.create_index("ix_evidence_inquiry_id", "evidence", ["inquiry_id"])
    op.create_index("ix_evidence_inquiry_captured", "evidence", ["inquiry_id", "captured_at"])
    op.create_index("ix_evidence_content_hash", "evidence", ["content_hash"])

    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="INFERRED"),
        sa.Column("origin", sa.String(16), nullable=False, server_default="AI"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('CONFIRMED','INFERRED','NEEDS_CONFIRMATION','INSUFFICIENT_DATA','UNAVAILABLE')",
            name="ck_insights_status",
        ),
        sa.CheckConstraint("origin IN ('AI','HUMAN')", name="ck_insights_origin"),
    )
    op.create_index("ix_insights_inquiry_id", "insights", ["inquiry_id"])
    op.create_index("ix_insights_inquiry_status", "insights", ["inquiry_id", "status"])

    op.create_table(
        "insight_evidence",
        sa.Column("insight_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insights.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("support_type", sa.String(16), nullable=False, server_default="SUPPORTS"),
        sa.CheckConstraint("support_type IN ('SUPPORTS','CONTRADICTS','CONTEXT')", name="ck_insight_evidence_support"),
    )


def downgrade() -> None:
    op.drop_table("insight_evidence")
    op.drop_index("ix_insights_inquiry_status", table_name="insights")
    op.drop_index("ix_insights_inquiry_id", table_name="insights")
    op.drop_table("insights")
    op.drop_index("ix_evidence_content_hash", table_name="evidence")
    op.drop_index("ix_evidence_inquiry_captured", table_name="evidence")
    op.drop_index("ix_evidence_inquiry_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("source_providers")
