import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class InquiryExtractionRecord(Base):
    __tablename__ = "inquiry_extractions"
    __table_args__ = (
        CheckConstraint("status IN ('SUCCESS','FAILED')", name="ck_inquiry_extractions_status"),
        Index("ix_inquiry_extractions_inquiry_created", "inquiry_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inquiries.id", ondelete="CASCADE"))
    llm_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="SET NULL"))
    structured_data: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    provider_code: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
