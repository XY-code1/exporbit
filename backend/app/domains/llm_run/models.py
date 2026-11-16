import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class LLMRun(Base):
    """One LLM provider call: purpose, model, usage, latency, status, input hash.

    Raw prompt text is never stored here; only the sha256 input hash, so usage
    can be audited without persisting sensitive inquiry text (docs/PROVIDER_DESIGN.md).
    """

    __tablename__ = "llm_runs"
    __table_args__ = (
        CheckConstraint("status IN ('SUCCESS','PROVIDER_ERROR')", name="ck_llm_runs_status"),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0",
            name="ck_llm_runs_tokens_nonnegative",
        ),
        Index("ix_llm_runs_purpose_created", "purpose", "created_at"),
        Index("ix_llm_runs_inquiry_created", "inquiry_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(64))
    provider_code: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_hash: Mapped[str] = mapped_column(String(64))
    inquiry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inquiries.id", ondelete="SET NULL"))
    repair_used: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
