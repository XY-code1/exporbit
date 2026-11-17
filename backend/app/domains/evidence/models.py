"""Evidence provenance aggregates: providers, evidence snapshots, insights, links.

Rules from docs/DATA_MODEL_DESIGN.md and docs/PROVIDER_DESIGN.md:
- Evidence keeps a snapshot, hash, captured time, source mode and demo flag.
- `is_demo` is machine-enforced to match `provider_mode = 'DEMO'`.
- Providers are disabled, never deleted, and provider deletion keeps evidence.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class SourceProvider(Base):
    __tablename__ = "source_providers"
    __table_args__ = (
        CheckConstraint("mode IN ('LIVE','MANUAL','DEMO','PLANNED')", name="ck_source_providers_mode"),
        CheckConstraint(
            "category IS NULL OR category IN ('CUSTOMER_INQUIRY','ENTERPRISE','ZHIHU','OFFICIAL','OVERSEAS')",
            name="ck_source_providers_category",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    category: Mapped[str | None] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("availability_status IN ('AVAILABLE','UNAVAILABLE')", name="ck_evidence_availability"),
        CheckConstraint(
            "credibility_status IN ('CONFIRMED','INFERRED','NEEDS_CONFIRMATION','INSUFFICIENT_DATA','UNAVAILABLE')",
            name="ck_evidence_credibility",
        ),
        CheckConstraint("is_demo = (provider_mode = 'DEMO')", name="ck_evidence_demo_flag_matches_mode"),
        CheckConstraint("length(trim(captured_text)) > 0", name="ck_evidence_snapshot_not_empty"),
        Index("ix_evidence_inquiry_captured", "inquiry_id", "captured_at"),
        Index("ix_evidence_content_hash", "content_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_providers.id", ondelete="SET NULL")
    )
    source_category: Mapped[str] = mapped_column(String(32))
    provider_mode: Mapped[str] = mapped_column(String(16))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[str] = mapped_column(String(300))
    canonical_url: Mapped[str | None] = mapped_column(String(500))
    captured_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    availability_status: Mapped[str] = mapped_column(String(16), default="AVAILABLE")
    credibility_status: Mapped[str] = mapped_column(String(32), default="NEEDS_CONFIRMATION")
    captured_by: Mapped[str | None] = mapped_column(String(80))
    usage_note: Mapped[str | None] = mapped_column(String(500))


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CONFIRMED','INFERRED','NEEDS_CONFIRMATION','INSUFFICIENT_DATA','UNAVAILABLE')",
            name="ck_insights_status",
        ),
        CheckConstraint("origin IN ('AI','HUMAN')", name="ck_insights_origin"),
        Index("ix_insights_inquiry_status", "inquiry_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="INFERRED")
    origin: Mapped[str] = mapped_column(String(16), default="AI")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InsightEvidence(Base):
    __tablename__ = "insight_evidence"
    __table_args__ = (
        CheckConstraint("support_type IN ('SUPPORTS','CONTRADICTS','CONTEXT')", name="ck_insight_evidence_support"),
    )
    insight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insights.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"), primary_key=True
    )
    support_type: Mapped[str] = mapped_column(String(16), default="SUPPORTS")
