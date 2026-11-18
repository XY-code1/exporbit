"""Evidence, insight and provenance API tests (synthetic data only)."""
import app.api.evidence as evidence_api
from app.providers.knowledge import DemoZhihuProvider
from app.providers.knowledge.contracts import KnowledgeErrorCode, KnowledgeProviderError
from tests.conftest import requires_db

pytestmark = requires_db


def create_inquiry(client, subject="Evidence API test"):
    response = client.post(
        "/api/v1/inquiries",
        json={
            "subject": subject,
            "raw_text": "Synthetic RFQ: 500 wireless earbuds for the German market.",
            "source_type": "TEXT",
        },
    )
    assert response.status_code == 201
    return response.json()


def manual_payload(**overrides):
    payload = {
        "kind": "MANUAL",
        "title": "客户邮件摘要（手工导入，合成）",
        "content": "客户要求包装印回收标识，并询问 CE 文件。合成测试内容。",
        "source_category": "CUSTOMER_INQUIRY",
        "captured_by": "tester",
    }
    payload.update(overrides)
    return payload


class UnavailableDemoProvider(DemoZhihuProvider):
    async def fetch(self, query: str):
        raise KnowledgeProviderError(KnowledgeErrorCode.UNAVAILABLE, "demo provider is offline")


def test_providers_are_listed_with_mode_and_no_secrets(client):
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    items = response.json()["items"]
    by_code = {item["code"]: item for item in items}
    assert {"fixture_live", "zhihu_demo", "manual_import", "zhihu_live"} <= set(by_code)
    assert by_code["zhihu_demo"]["mode"] == "DEMO"
    assert by_code["zhihu_live"]["mode"] == "PLANNED"
    assert by_code["zhihu_live"]["enabled"] is False
    assert set(items[0]) == {"code", "category", "display_name", "mode", "enabled", "last_health_status"}


def test_manual_evidence_capture_and_list(client):
    inquiry = create_inquiry(client)
    created = client.post(f'/api/v1/inquiries/{inquiry["id"]}/evidence', json=manual_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "CAPTURED"
    assert body["provider_code"] == "manual_import"
    assert body["provider_mode"] == "MANUAL"
    evidence = body["evidence"]
    assert evidence["is_demo"] is False
    assert evidence["snapshot_verified"] is True
    assert evidence["captured_by"] == "tester"
    assert evidence["credibility_status"] == "NEEDS_CONFIRMATION"
    assert evidence["captured_text"].startswith("客户要求包装")

    listed = client.get(f'/api/v1/inquiries/{inquiry["id"]}/evidence')
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [evidence["id"]]


def test_empty_manual_evidence_is_rejected(client):
    inquiry = create_inquiry(client)
    response = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json=manual_payload(content="   "),
    )
    assert response.status_code == 422
    assert client.get(f'/api/v1/inquiries/{inquiry["id"]}/evidence').json()["items"] == []


def test_demo_capture_is_labelled_and_not_presented_as_live(client):
    inquiry = create_inquiry(client)
    response = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "zhihu_demo", "query": "Germany earbuds"},
    )
    assert response.status_code == 201
    evidence = response.json()["evidence"]
    assert response.json()["provider_mode"] == "DEMO"
    assert evidence["is_demo"] is True
    assert evidence["provider_code"] == "zhihu_demo"
    assert "DEMO" in evidence["title"]
    assert "not a live Zhihu integration" in evidence["usage_note"]


def test_synthetic_fixture_and_planned_provider_are_not_capturable(client):
    inquiry = create_inquiry(client)
    fixture = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "fixture_live"},
    )
    assert fixture.status_code == 409
    assert fixture.json()["error"]["code"] == "PROVIDER_NOT_AVAILABLE"

    planned = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "zhihu_live"},
    )
    assert planned.status_code == 409
    assert planned.json()["error"]["code"] == "PROVIDER_NOT_AVAILABLE"

    unknown = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "does_not_exist"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "PROVIDER_NOT_FOUND"


def test_provider_outage_returns_unavailable_without_creating_evidence(client, monkeypatch):
    monkeypatch.setitem(evidence_api.CAPTURE_PROVIDERS, "zhihu_demo", UnavailableDemoProvider)
    inquiry = create_inquiry(client)
    response = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "zhihu_demo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNAVAILABLE"
    assert body["error_code"] == "PROVIDER_UNAVAILABLE"
    assert body["evidence"] is None
    assert client.get(f'/api/v1/inquiries/{inquiry["id"]}/evidence').json()["items"] == []


def test_insight_requires_existing_evidence_from_the_same_inquiry(client):
    first = create_inquiry(client, "First")
    second = create_inquiry(client, "Second")
    evidence = client.post(f'/api/v1/inquiries/{first["id"]}/evidence', json=manual_payload()).json()["evidence"]

    missing = client.post(
        f'/api/v1/inquiries/{first["id"]}/insights',
        json={"statement": "无证据的推断", "evidence_links": []},
    )
    assert missing.status_code == 422

    cross = client.post(
        f'/api/v1/inquiries/{second["id"]}/insights',
        json={"statement": "跨询盘引用", "evidence_links": [{"evidence_id": evidence["id"]}]},
    )
    assert cross.status_code == 400
    assert cross.json()["error"]["code"] == "EVIDENCE_INQUIRY_MISMATCH"

    duplicate = client.post(
        f'/api/v1/inquiries/{first["id"]}/insights',
        json={
            "statement": "重复引用",
            "evidence_links": [{"evidence_id": evidence["id"]}, {"evidence_id": evidence["id"]}],
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_EVIDENCE_LINK"


def test_insight_provenance_and_evidence_associations(client):
    inquiry = create_inquiry(client)
    manual = client.post(f'/api/v1/inquiries/{inquiry["id"]}/evidence', json=manual_payload()).json()["evidence"]
    demo = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/evidence',
        json={"kind": "PROVIDER", "provider_code": "zhihu_demo"},
    ).json()["evidence"]

    created = client.post(
        f'/api/v1/inquiries/{inquiry["id"]}/insights',
        json={
            "statement": "回复时应说明 CE 文件并确认包装回收标识（演示）",
            "status": "INFERRED",
            "evidence_links": [
                {"evidence_id": manual["id"], "support_type": "SUPPORTS"},
                {"evidence_id": demo["id"], "support_type": "CONTEXT"},
            ],
        },
    )
    assert created.status_code == 201
    insight = created.json()
    assert insight["origin"] == "HUMAN"
    assert insight["revision"] == 1
    assert {link["support_type"] for link in insight["evidence_links"]} == {"SUPPORTS", "CONTEXT"}

    listed = client.get(f'/api/v1/inquiries/{inquiry["id"]}/insights')
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [insight["id"]]

    provenance = client.get(f'/api/v1/insights/{insight["id"]}/provenance')
    assert provenance.status_code == 200
    chain = provenance.json()
    assert len(chain["evidence"]) == 2
    assert all(item["snapshot_verified"] for item in chain["evidence"])
    demo_entry = next(item for item in chain["evidence"] if item["provider_code"] == "zhihu_demo")
    assert demo_entry["is_demo"] is True
    assert demo_entry["snapshot_chars"] > 0

    detail = client.get(f'/api/v1/evidence/{manual["id"]}')
    assert detail.status_code == 200
    assert detail.json()["insights"][0]["insight_id"] == insight["id"]
    assert detail.json()["insights"][0]["support_type"] == "SUPPORTS"


def test_unknown_resources_return_404(client):
    inquiry = create_inquiry(client)
    missing_inquiry = client.get("/api/v1/inquiries/00000000-0000-0000-0000-000000000000/evidence")
    assert missing_inquiry.status_code == 404
    assert missing_inquiry.json()["error"]["code"] == "INQUIRY_NOT_FOUND"

    missing_evidence = client.get("/api/v1/evidence/00000000-0000-0000-0000-000000000000")
    assert missing_evidence.status_code == 404
    assert missing_evidence.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"

    missing_insight = client.get("/api/v1/insights/00000000-0000-0000-0000-000000000000/provenance")
    assert missing_insight.status_code == 404
    assert missing_insight.json()["error"]["code"] == "INSIGHT_NOT_FOUND"

    assert client.get(f'/api/v1/inquiries/{inquiry["id"]}/insights').json()["items"] == []
