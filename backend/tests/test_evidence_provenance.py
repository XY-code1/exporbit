"""POC-05 provenance tests against the PostgreSQL test database."""
import asyncio
from dataclasses import replace

import pytest
from sqlalchemy import update

from app.core.errors import AppError
from app.domains.evidence.models import Evidence
from app.domains.evidence.service import EvidenceService, content_hash
from app.domains.inquiry.models import Inquiry
from app.infrastructure.database import SessionLocal
from app.providers.knowledge import DemoZhihuProvider, FixtureLiveProvider
from app.providers.knowledge.contracts import ProviderMode, SourceCategory
from tests.conftest import requires_db

pytestmark = requires_db


def _make_inquiry(session, raw_text: str = "We need 500 wireless earbuds, FOB Shenzhen.") -> Inquiry:
    inquiry = Inquiry(
        subject="POC-05 provenance test",
        raw_text=raw_text,
        source_type="TEXT",
        workflow_status="NEW",
        extracted_fields={},
        content_hash=content_hash(raw_text),
    )
    session.add(inquiry)
    session.commit()
    return inquiry


def _capture(service: EvidenceService, inquiry_id, provider, query: str = "EU import requirements"):
    return asyncio.run(service.capture_from_provider(inquiry_id, provider, query))


class MislabeledDemoProvider(DemoZhihuProvider):
    async def fetch(self, query: str):
        document = await super().fetch(query)
        return replace(document, is_demo=False)


class PlannedProvider:
    code = "zhihu_live"
    category = SourceCategory.ZHIHU
    mode = ProviderMode.PLANNED

    async def fetch(self, query: str):
        raise AssertionError("planned provider must never be fetched")

    async def health(self):
        raise AssertionError("planned provider must never be fetched")


def test_live_capture_persists_snapshot_and_hash() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        provider = FixtureLiveProvider()
        outcome = _capture(service, inquiry.id, provider)
        assert outcome.status == "CAPTURED"
        evidence = service.get_evidence(outcome.evidence_id)
        assert evidence.provider_mode == "LIVE"
        assert evidence.is_demo is False
        assert evidence.availability_status == "AVAILABLE"
        assert evidence.credibility_status == "NEEDS_CONFIRMATION"
        assert evidence.captured_text == provider.content.strip()
        assert evidence.content_hash == content_hash(provider.content.strip())
        assert service.snapshot_verified(evidence)


def test_demo_evidence_is_always_labelled() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        outcome = _capture(service, inquiry.id, DemoZhihuProvider())
        evidence = service.get_evidence(outcome.evidence_id)
        assert evidence.provider_mode == "DEMO"
        assert evidence.is_demo is True
        insight = service.create_insight(
            inquiry.id, statement="德国买家可能关注 CE 与德语说明书（演示）", evidence_links=[(evidence.id, "SUPPORTS")]
        )
        provenance = service.provenance(insight.id)
        assert provenance.evidence[0].is_demo is True
        assert provenance.evidence[0].provider_mode == "DEMO"


def test_mislabeled_demo_document_is_rejected() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        with pytest.raises(AppError) as caught:
            _capture(service, inquiry.id, MislabeledDemoProvider())
        assert caught.value.code == "PROVIDER_MISMATCH"
        assert service.list_evidence(inquiry.id) == []


def test_manual_evidence_records_mode_and_operator() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        evidence = service.capture_manual(
            inquiry.id,
            title="客户邮件摘要（手工导入）",
            content="客户提到包装需印回收标识。手工导入的合成示例。",
            canonical_url=None,
            captured_by="operator-1",
        )
        assert evidence.provider_mode == "MANUAL"
        assert evidence.source_category == "CUSTOMER_INQUIRY"
        assert evidence.is_demo is False
        assert evidence.captured_by == "operator-1"
        assert service.snapshot_verified(evidence)


def test_insight_provenance_chain_covers_every_evidence() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        live = service.get_evidence(_capture(service, inquiry.id, FixtureLiveProvider()).evidence_id)
        demo = service.get_evidence(_capture(service, inquiry.id, DemoZhihuProvider()).evidence_id)
        manual = service.capture_manual(
            inquiry.id,
            title="客户邮件摘要（手工导入）",
            content="客户要求德语说明书。合成示例。",
        )
        insight = service.create_insight(
            inquiry.id,
            statement="回复时应提及 CE 文件并询问包装要求",
            evidence_links=[(live.id, "SUPPORTS"), (demo.id, "CONTEXT"), (manual.id, "SUPPORTS")],
        )
        provenance = service.provenance(insight.id)
        assert len(provenance.evidence) == 3
        assert {item.support_type for item in provenance.evidence} == {"SUPPORTS", "CONTEXT"}
        assert {item.provider_code for item in provenance.evidence} == {"fixture_live", "zhihu_demo", "manual_import"}
        assert all(item.snapshot_verified for item in provenance.evidence)
        assert all(item.snapshot_text for item in provenance.evidence)


def test_provider_outage_keeps_prior_provenance_readable() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        provider = FixtureLiveProvider()
        first = _capture(service, inquiry.id, provider)
        insight = service.create_insight(
            inquiry.id, statement="需要 CE 文件", evidence_links=[(first.evidence_id, "SUPPORTS")]
        )
        provider.go_offline()
        outage = _capture(service, inquiry.id, provider)
        assert outage.status == "UNAVAILABLE"
        assert outage.error_code == "PROVIDER_UNAVAILABLE"
        assert outage.evidence_id is None
        assert len(service.list_evidence(inquiry.id)) == 1
        provenance = service.provenance(insight.id)
        assert len(provenance.evidence) == 1
        assert provenance.evidence[0].snapshot_verified
        assert "PROV-TOKEN-EU-01" in provenance.evidence[0].snapshot_text
        row = next(item for item in service.list_providers() if item.code == "fixture_live")
        assert row.last_health_status == "UNAVAILABLE"


def test_expired_external_link_keeps_snapshot() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        outcome = _capture(service, inquiry.id, FixtureLiveProvider())
        insight = service.create_insight(
            inquiry.id, statement="需要核实欧盟合规文件", evidence_links=[(outcome.evidence_id, "SUPPORTS")]
        )
        service.mark_unavailable(outcome.evidence_id)
        provenance = service.provenance(insight.id)
        assert provenance.evidence[0].availability_status == "UNAVAILABLE"
        assert provenance.evidence[0].snapshot_verified
        assert "PROV-TOKEN-EU-01" in provenance.evidence[0].snapshot_text


def test_insight_requires_evidence() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        with pytest.raises(AppError) as caught:
            service.create_insight(inquiry.id, statement="无证据的推断", evidence_links=[])
        assert caught.value.code == "EVIDENCE_REQUIRED"


def test_cross_inquiry_evidence_link_rejected() -> None:
    with SessionLocal() as session:
        first = _make_inquiry(session)
        second = _make_inquiry(session, raw_text="Second synthetic inquiry with enough text.")
        service = EvidenceService(session)
        evidence = service.get_evidence(_capture(service, first.id, FixtureLiveProvider()).evidence_id)
        with pytest.raises(AppError) as caught:
            service.create_insight(second.id, statement="跨询盘引用", evidence_links=[(evidence.id, "SUPPORTS")])
        assert caught.value.code == "EVIDENCE_INQUIRY_MISMATCH"


def test_planned_provider_cannot_capture() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        service.seed_providers()
        with pytest.raises(AppError) as caught:
            _capture(service, inquiry.id, PlannedProvider())
        assert caught.value.code == "PROVIDER_NOT_AVAILABLE"


def test_snapshot_hash_detects_tampering() -> None:
    with SessionLocal() as session:
        inquiry = _make_inquiry(session)
        service = EvidenceService(session)
        outcome = _capture(service, inquiry.id, FixtureLiveProvider())
        session.execute(
            update(Evidence).where(Evidence.id == outcome.evidence_id).values(captured_text="tampered snapshot")
        )
        session.commit()
        session.expire_all()
        evidence = service.get_evidence(outcome.evidence_id)
        assert service.snapshot_verified(evidence) is False
