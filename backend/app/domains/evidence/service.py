"""Evidence and insight provenance service (POC-05).

Captures provider or manual evidence with an immutable text snapshot and sha256
hash, links insights to their evidence, and keeps provenance readable after a
provider outage or an expired external link. DEMO evidence is machine-labelled
from the registered provider mode; callers cannot override it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.evidence.models import Evidence, Insight, InsightEvidence, SourceProvider
from app.domains.inquiry.models import Inquiry
from app.providers.knowledge.contracts import (
    KnowledgeProvider,
    KnowledgeProviderError,
    ProviderMode,
    SourceCategory,
    SourceDocument,
)
from app.providers.knowledge.fixtures import PROVIDER_SEEDS

SUPPORT_TYPES = {"SUPPORTS", "CONTRADICTS", "CONTEXT"}
INSIGHT_STATUSES = {"CONFIRMED", "INFERRED", "NEEDS_CONFIRMATION", "INSUFFICIENT_DATA", "UNAVAILABLE"}
INSIGHT_ORIGINS = {"AI", "HUMAN"}


@dataclass(frozen=True)
class CaptureOutcome:
    status: str  # CAPTURED | UNAVAILABLE
    provider_code: str
    provider_mode: str
    evidence_id: UUID | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class EvidenceProvenance:
    evidence_id: UUID
    support_type: str
    title: str
    canonical_url: str | None
    provider_code: str | None
    provider_mode: str
    source_category: str
    is_demo: bool
    availability_status: str
    captured_at: datetime
    source_published_at: datetime | None
    content_hash: str
    snapshot_verified: bool
    snapshot_chars: int
    snapshot_text: str


@dataclass(frozen=True)
class InsightProvenance:
    insight_id: UUID
    inquiry_id: UUID
    statement: str
    status: str
    origin: str
    revision: int
    evidence: tuple[EvidenceProvenance, ...]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EvidenceService:
    def __init__(self, session: Session):
        self.session = session

    # -- providers ---------------------------------------------------------

    def seed_providers(self) -> dict[str, SourceProvider]:
        providers = {row.code: row for row in self.session.scalars(select(SourceProvider))}
        added = False
        for seed in PROVIDER_SEEDS:
            if seed["code"] in providers:
                continue
            provider = SourceProvider(**seed)
            self.session.add(provider)
            providers[seed["code"]] = provider
            added = True
        if added:
            self.session.commit()
        return providers

    def list_providers(self) -> list[SourceProvider]:
        self.seed_providers()
        return list(self.session.scalars(select(SourceProvider).order_by(SourceProvider.code)))

    def _provider(self, code: str, *, require_enabled: bool = False) -> SourceProvider:
        provider = self.session.scalar(select(SourceProvider).where(SourceProvider.code == code))
        if provider is None:
            self.seed_providers()
            provider = self.session.scalar(select(SourceProvider).where(SourceProvider.code == code))
        if provider is None:
            raise AppError("PROVIDER_NOT_FOUND", "Provider is not registered", 404, {"code": code})
        if require_enabled and (not provider.enabled or provider.mode == ProviderMode.PLANNED.value):
            raise AppError(
                "PROVIDER_NOT_AVAILABLE",
                "Provider is disabled or only planned",
                409,
                {"code": provider.code, "mode": provider.mode},
            )
        return provider

    # -- capture -----------------------------------------------------------

    async def capture_from_provider(
        self, inquiry_id: UUID, provider: KnowledgeProvider, query: str
    ) -> CaptureOutcome:
        self._require_inquiry(inquiry_id)
        row = self._provider(provider.code, require_enabled=True)
        if row.mode != provider.mode.value or row.category != provider.category.value:
            raise AppError(
                "PROVIDER_MISMATCH",
                "Provider adapter does not match the registered provider",
                500,
                {"code": row.code, "registered_mode": row.mode, "adapter_mode": provider.mode.value},
            )
        try:
            document = await provider.fetch(query)
        except KnowledgeProviderError as exc:
            row.last_health_status = "UNAVAILABLE"
            self.session.commit()
            # Provider failure is isolated: callers keep prior evidence and insights.
            return CaptureOutcome(
                status="UNAVAILABLE", provider_code=row.code, provider_mode=row.mode, error_code=exc.code.value
            )
        evidence = self._persist_document(inquiry_id, row, document)
        row.last_health_status = "AVAILABLE"
        self.session.commit()
        return CaptureOutcome(
            status="CAPTURED", provider_code=row.code, provider_mode=row.mode, evidence_id=evidence.id
        )

    def capture_manual(
        self,
        inquiry_id: UUID,
        *,
        title: str,
        content: str,
        canonical_url: str | None = None,
        source_category: str = SourceCategory.CUSTOMER_INQUIRY.value,
        captured_by: str = "local-demo",
        source_published_at: datetime | None = None,
        usage_note: str | None = None,
    ) -> Evidence:
        self._require_inquiry(inquiry_id)
        if source_category not in {category.value for category in SourceCategory}:
            raise AppError("SOURCE_CATEGORY_INVALID", "Unknown source category", 400, {"category": source_category})
        row = self._provider("manual_import", require_enabled=True)
        evidence = self._insert_evidence(
            inquiry_id,
            provider_id=row.id,
            title=title,
            canonical_url=canonical_url,
            content=content,
            source_category=source_category,
            provider_mode=ProviderMode.MANUAL.value,
            is_demo=False,
            captured_by=captured_by,
            source_published_at=source_published_at,
            usage_note=usage_note,
        )
        self.session.commit()
        return evidence

    def _persist_document(self, inquiry_id: UUID, row: SourceProvider, document: SourceDocument) -> Evidence:
        is_demo = row.mode == ProviderMode.DEMO.value
        if document.provider_mode.value != row.mode or document.is_demo is not is_demo:
            raise AppError(
                "PROVIDER_MISMATCH",
                "Provider document metadata does not match the registered mode",
                500,
                {"code": row.code, "registered_mode": row.mode, "document_mode": document.provider_mode.value},
            )
        if row.category and document.source_category.value != row.category:
            raise AppError(
                "PROVIDER_MISMATCH",
                "Provider document category does not match the registered category",
                500,
                {"code": row.code, "registered_category": row.category, "document_category": document.source_category.value},
            )
        return self._insert_evidence(
            inquiry_id,
            provider_id=row.id,
            title=document.title,
            canonical_url=document.canonical_url,
            content=document.content,
            source_category=document.source_category.value,
            provider_mode=row.mode,
            is_demo=is_demo,
            captured_by=None,
            source_published_at=document.published_at,
            usage_note=document.usage_note,
        )

    def _insert_evidence(
        self,
        inquiry_id: UUID,
        *,
        provider_id: UUID | None,
        title: str,
        canonical_url: str | None,
        content: str,
        source_category: str,
        provider_mode: str,
        is_demo: bool,
        captured_by: str | None,
        source_published_at: datetime | None,
        usage_note: str | None,
    ) -> Evidence:
        text = content.strip()
        if not text:
            raise AppError("EVIDENCE_EMPTY", "Evidence snapshot is empty", 400)
        evidence = Evidence(
            inquiry_id=inquiry_id,
            provider_id=provider_id,
            source_category=source_category,
            provider_mode=provider_mode,
            is_demo=is_demo,
            title=title.strip()[:300],
            canonical_url=canonical_url,
            captured_text=text,
            content_hash=content_hash(text),
            source_published_at=source_published_at,
            captured_at=datetime.now(timezone.utc),
            availability_status="AVAILABLE",
            credibility_status="NEEDS_CONFIRMATION",
            captured_by=captured_by,
            usage_note=usage_note,
        )
        self.session.add(evidence)
        self.session.flush()
        return evidence

    # -- evidence reads and availability ----------------------------------

    def get_evidence(self, evidence_id: UUID) -> Evidence:
        evidence = self.session.get(Evidence, evidence_id)
        if evidence is None:
            raise AppError("EVIDENCE_NOT_FOUND", "Evidence not found", 404, {"evidence_id": str(evidence_id)})
        return evidence

    def list_evidence(self, inquiry_id: UUID) -> list[Evidence]:
        self._require_inquiry(inquiry_id)
        return list(
            self.session.scalars(
                select(Evidence).where(Evidence.inquiry_id == inquiry_id).order_by(Evidence.captured_at.desc())
            )
        )

    def mark_unavailable(self, evidence_id: UUID) -> Evidence:
        """External link expired: keep the snapshot, flag availability only."""
        evidence = self.get_evidence(evidence_id)
        evidence.availability_status = "UNAVAILABLE"
        self.session.commit()
        return evidence

    def snapshot_verified(self, evidence: Evidence) -> bool:
        return content_hash(evidence.captured_text) == evidence.content_hash

    # -- insights and provenance ------------------------------------------

    def create_insight(
        self,
        inquiry_id: UUID,
        *,
        statement: str,
        evidence_links: list[tuple[UUID, str]],
        status: str = "INFERRED",
        origin: str = "AI",
    ) -> Insight:
        self._require_inquiry(inquiry_id)
        if status not in INSIGHT_STATUSES or origin not in INSIGHT_ORIGINS:
            raise AppError("INSIGHT_STATUS_INVALID", "Unsupported insight status or origin", 400)
        text = statement.strip()
        if not text:
            raise AppError("INSIGHT_EMPTY", "Insight statement is empty", 400)
        if not evidence_links:
            raise AppError("EVIDENCE_REQUIRED", "An insight requires at least one evidence link", 400)
        evidence_ids = [evidence_id for evidence_id, _ in evidence_links]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise AppError("DUPLICATE_EVIDENCE_LINK", "Evidence is linked more than once", 400)
        for _, support_type in evidence_links:
            if support_type not in SUPPORT_TYPES:
                raise AppError("SUPPORT_TYPE_INVALID", "Unsupported support type", 400, {"support_type": support_type})
        rows = {row.id: row for row in self.session.scalars(select(Evidence).where(Evidence.id.in_(evidence_ids)))}
        missing = [str(evidence_id) for evidence_id in evidence_ids if evidence_id not in rows]
        if missing:
            raise AppError("EVIDENCE_NOT_FOUND", "Linked evidence does not exist", 404, {"missing": missing})
        foreign = [str(row.id) for row in rows.values() if row.inquiry_id != inquiry_id]
        if foreign:
            raise AppError(
                "EVIDENCE_INQUIRY_MISMATCH",
                "Evidence belongs to a different inquiry",
                400,
                {"evidence_ids": foreign},
            )
        insight = Insight(inquiry_id=inquiry_id, statement=text, status=status, origin=origin)
        self.session.add(insight)
        self.session.flush()
        for evidence_id, support_type in evidence_links:
            self.session.add(InsightEvidence(insight_id=insight.id, evidence_id=evidence_id, support_type=support_type))
        self.session.commit()
        return insight

    def provenance(self, insight_id: UUID) -> InsightProvenance:
        insight = self.session.get(Insight, insight_id)
        if insight is None:
            raise AppError("INSIGHT_NOT_FOUND", "Insight not found", 404, {"insight_id": str(insight_id)})
        rows = self.session.execute(
            select(InsightEvidence, Evidence, SourceProvider)
            .join(Evidence, InsightEvidence.evidence_id == Evidence.id)
            .outerjoin(SourceProvider, Evidence.provider_id == SourceProvider.id)
            .where(InsightEvidence.insight_id == insight_id)
            .order_by(Evidence.captured_at, Evidence.id)
        ).all()
        evidence = tuple(
            EvidenceProvenance(
                evidence_id=item.id,
                support_type=link.support_type,
                title=item.title,
                canonical_url=item.canonical_url,
                provider_code=provider.code if provider else None,
                provider_mode=item.provider_mode,
                source_category=item.source_category,
                is_demo=item.is_demo,
                availability_status=item.availability_status,
                captured_at=item.captured_at,
                source_published_at=item.source_published_at,
                content_hash=item.content_hash,
                snapshot_verified=self.snapshot_verified(item),
                snapshot_chars=len(item.captured_text),
                snapshot_text=item.captured_text,
            )
            for link, item, provider in rows
        )
        return InsightProvenance(
            insight_id=insight.id,
            inquiry_id=insight.inquiry_id,
            statement=insight.statement,
            status=insight.status,
            origin=insight.origin,
            revision=insight.revision,
            evidence=evidence,
        )

    def _require_inquiry(self, inquiry_id: UUID) -> None:
        if self.session.scalar(select(Inquiry.id).where(Inquiry.id == inquiry_id)) is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
