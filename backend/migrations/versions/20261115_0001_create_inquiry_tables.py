"""create customer and inquiry tables

Revision ID: 20261115_0001
Revises: None
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261115_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("profile", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_customers_legal_name", "customers", [sa.text("lower(legal_name)")])
    op.create_table(
        "inquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("workflow_status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(raw_text)) >= 10", name="ck_inquiries_raw_text_min_length"),
        sa.CheckConstraint("source_type IN ('TEXT','PDF','IMAGE','EML')", name="ck_inquiries_source_type"),
        sa.CheckConstraint("workflow_status IN ('NEW','ANALYZING','NEEDS_INFORMATION','READY_TO_REPLY','COMPLETED','FAILED')", name="ck_inquiries_workflow_status"),
    )
    op.create_index("ix_inquiries_status_updated", "inquiries", ["workflow_status", sa.text("updated_at DESC")])
    op.create_index("ix_inquiries_customer_created", "inquiries", ["customer_id", sa.text("created_at DESC")])
    op.create_index("ix_inquiries_content_hash_customer", "inquiries", ["content_hash", "customer_id"])


def downgrade() -> None:
    op.drop_table("inquiries")
    op.drop_table("customers")

