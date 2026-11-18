from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.evidence.models import Evidence, Insight, SourceProvider
from app.domains.evidence.schemas import (
    EvidenceCaptureRequest,
    EvidenceDetail,
    EvidenceInsightLink,
    EvidenceList,
    EvidenceProvenanceRead,
    EvidenceRead,
    EvidenceSaveResponse,
    InsightCreate,
    InsightEvidenceLinkRead,
    InsightList,
    InsightProvenanceRead,
    InsightRead,
    ProviderList,
    ProviderRead,
)
from app.domains.evidence.service import EvidenceService
from app.infrastructure.database import get_session
from app.providers.knowledge import DemoZhihuProvider
from app.providers.knowledge.contracts import KnowledgeProvider

router = APIRouter(tags=["evidence"])

# Only adapters that exist may be executed. The POC `fixture_live` provider is
# intentionally absent: it is synthetic data marked LIVE-like for provenance
# tests, not a validated external integration.
CAPTURE_PROVIDERS: dict[str, Callable[[], KnowledgeProvider]] = {
    "zhihu_demo": DemoZhihuProvider,
}


def _provider_code(session: Session, evidence: Evidence) -> str | None:
    if evidence.provider_id is None:
        return None
    provider = session.get(SourceProvider, evidence.provider_id)
    return provider.code if provider else None


def _evidence_read(session: Session, service: EvidenceService, evidence: Evidence) -> EvidenceRead:
    return EvidenceRead(
        id=evidence.id,
        inquiry_id=evidence.inquiry_id,
        provider_code=_provider_code(session, evidence),
        source_category=evidence.source_category,
        provider_mode=evidence.provider_mode,
        is_demo=evidence.is_demo,
        title=evidence.title,
        canonical_url=evidence.canonical_url,
        captured_text=evidence.captured_text,
        content_hash=evidence.content_hash,
        snapshot_verified=service.snapshot_verified(evidence),
        source_published_at=evidence.source_published_at,
        captured_at=evidence.captured_at,
        availability_status=evidence.availability_status,
        credibility_status=evidence.credibility_status,
        captured_by=evidence.captured_by,
        usage_note=evidence.usage_note,
    )


def _insight_read(insight: Insight, links: list[tuple[UUID, str]]) -> InsightRead:
    return InsightRead(
        id=insight.id,
        inquiry_id=insight.inquiry_id,
        statement=insight.statement,
        status=insight.status,
        origin=insight.origin,
        revision=insight.revision,
        created_at=insight.created_at,
        updated_at=insight.updated_at,
        evidence_links=[InsightEvidenceLinkRead(evidence_id=evidence_id, support_type=support_type) for evidence_id, support_type in links],
    )


@router.get("/providers", response_model=ProviderList)
def list_providers(session: Session = Depends(get_session)):
    rows = EvidenceService(session).list_providers()
    return ProviderList(
        items=[
            ProviderRead(
                code=row.code,
                category=row.category,
                display_name=row.display_name,
                mode=row.mode,
                enabled=row.enabled,
                last_health_status=row.last_health_status,
            )
            for row in rows
        ]
    )


@router.get("/inquiries/{inquiry_id}/evidence", response_model=EvidenceList)
def list_inquiry_evidence(inquiry_id: UUID, session: Session = Depends(get_session)):
    service = EvidenceService(session)
    return EvidenceList(items=[_evidence_read(session, service, row) for row in service.list_evidence(inquiry_id)])


@router.post(
    "/inquiries/{inquiry_id}/evidence",
    response_model=EvidenceSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_inquiry_evidence(
    inquiry_id: UUID,
    payload: EvidenceCaptureRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    service = EvidenceService(session)
    if payload.kind == "MANUAL":
        evidence = service.capture_manual(
            inquiry_id,
            title=payload.title or "",
            content=payload.content or "",
            canonical_url=payload.canonical_url,
            source_category=payload.source_category,
            captured_by=payload.captured_by or "local-user",
            source_published_at=payload.source_published_at,
            usage_note=payload.usage_note,
        )
        return EvidenceSaveResponse(
            status="CAPTURED",
            provider_code="manual_import",
            provider_mode="MANUAL",
            evidence=_evidence_read(session, service, evidence),
        )

    row = service.get_provider(payload.provider_code or "", require_enabled=True)
    factory = CAPTURE_PROVIDERS.get(row.code)
    if factory is None:
        raise AppError(
            "PROVIDER_NOT_AVAILABLE",
            "Provider has no executable capture adapter",
            409,
            {"code": row.code, "mode": row.mode},
        )
    outcome = await service.capture_from_provider(inquiry_id, factory(), payload.query)
    if outcome.status != "CAPTURED":
        # Provider failure is a normal, isolated result: no evidence is created.
        response.status_code = status.HTTP_200_OK
        return EvidenceSaveResponse(
            status="UNAVAILABLE",
            provider_code=outcome.provider_code,
            provider_mode=outcome.provider_mode,
            error_code=outcome.error_code,
        )
    evidence = service.get_evidence(outcome.evidence_id)
    return EvidenceSaveResponse(
        status="CAPTURED",
        provider_code=outcome.provider_code,
        provider_mode=outcome.provider_mode,
        evidence=_evidence_read(session, service, evidence),
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail)
def get_evidence(evidence_id: UUID, session: Session = Depends(get_session)):
    service = EvidenceService(session)
    evidence = service.get_evidence(evidence_id)
    base = _evidence_read(session, service, evidence)
    return EvidenceDetail(
        **base.model_dump(),
        insights=[
            EvidenceInsightLink(
                insight_id=insight.id,
                statement=insight.statement,
                status=insight.status,
                support_type=support_type,
            )
            for insight, support_type in service.evidence_insights(evidence_id)
        ],
    )


@router.get("/inquiries/{inquiry_id}/insights", response_model=InsightList)
def list_inquiry_insights(inquiry_id: UUID, session: Session = Depends(get_session)):
    service = EvidenceService(session)
    insights = service.list_insights(inquiry_id)
    links = service.insight_links([insight.id for insight in insights])
    return InsightList(items=[_insight_read(insight, links[insight.id]) for insight in insights])


@router.post(
    "/inquiries/{inquiry_id}/insights",
    response_model=InsightRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inquiry_insight(
    inquiry_id: UUID,
    payload: InsightCreate,
    session: Session = Depends(get_session),
):
    service = EvidenceService(session)
    insight = service.create_insight(
        inquiry_id,
        statement=payload.statement,
        evidence_links=[(link.evidence_id, link.support_type) for link in payload.evidence_links],
        status=payload.status,
        origin="HUMAN",
    )
    links = service.insight_links([insight.id])
    return _insight_read(insight, links[insight.id])


@router.get("/insights/{insight_id}/provenance", response_model=InsightProvenanceRead)
def get_insight_provenance(insight_id: UUID, session: Session = Depends(get_session)):
    provenance = EvidenceService(session).provenance(insight_id)
    return InsightProvenanceRead(
        insight_id=provenance.insight_id,
        inquiry_id=provenance.inquiry_id,
        statement=provenance.statement,
        status=provenance.status,
        origin=provenance.origin,
        revision=provenance.revision,
        evidence=[
            EvidenceProvenanceRead(
                evidence_id=item.evidence_id,
                support_type=item.support_type,
                title=item.title,
                canonical_url=item.canonical_url,
                provider_code=item.provider_code,
                provider_mode=item.provider_mode,
                source_category=item.source_category,
                is_demo=item.is_demo,
                availability_status=item.availability_status,
                captured_at=item.captured_at,
                source_published_at=item.source_published_at,
                content_hash=item.content_hash,
                snapshot_verified=item.snapshot_verified,
                snapshot_chars=item.snapshot_chars,
                snapshot_text=item.snapshot_text,
            )
            for item in provenance.evidence
        ],
    )
