import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class InquiryFile(Base):
    __tablename__ = "inquiry_files"
    __table_args__ = (
        CheckConstraint("parse_status IN ('SUCCESS','FAILED')", name="ck_inquiry_files_parse_status"),
        CheckConstraint("byte_size >= 0", name="ck_inquiry_files_byte_size_nonnegative"),
        Index("ix_inquiry_files_inquiry_created", "inquiry_id", "created_at"),
        Index("ix_inquiry_files_sha256", "sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=True
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    parsed_document: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
