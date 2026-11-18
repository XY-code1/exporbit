"""persist inquiry uploads and parsed document provenance

Revision ID: 20261118_0005
Revises: 20261117_0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261118_0005"
down_revision = "20261117_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inquiry_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(64), nullable=True, unique=True),
        sa.Column("parse_status", sa.String(16), nullable=False),
        sa.Column("parsed_document", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("parse_status IN ('SUCCESS','FAILED')", name="ck_inquiry_files_parse_status"),
        sa.CheckConstraint("byte_size >= 0", name="ck_inquiry_files_byte_size_nonnegative"),
    )
    op.create_index("ix_inquiry_files_inquiry_created", "inquiry_files", ["inquiry_id", "created_at"])
    op.create_index("ix_inquiry_files_sha256", "inquiry_files", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_inquiry_files_sha256", table_name="inquiry_files")
    op.drop_index("ix_inquiry_files_inquiry_created", table_name="inquiry_files")
    op.drop_table("inquiry_files")
