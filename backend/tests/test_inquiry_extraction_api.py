from copy import deepcopy

from app.api.inquiries import get_llm_provider
from app.domains.extraction.v2_schemas import StructuredInquiryExtraction
from app.providers.contracts import LLMResult, LLMUsage, ProviderError, ProviderErrorCode
from tests.test_extraction_v2_schema import valid_payload
from tests.conftest import requires_db

pytestmark = requires_db


class FakeProvider:
    model_name = "fake-deepseek"
    def __init__(self, error=None): self.error = error
    async def generate_structured(self, **kwargs):
        if self.error: raise self.error
        return LLMResult(data=StructuredInquiryExtraction.model_validate(valid_payload()), provider="deepseek", model=self.model_name, usage=LLMUsage(10,20,30), latency_ms=5, finish_reason="stop", raw_content="{}")


def create_inquiry(client):
    return client.post("/api/v1/inquiries", json={"subject":"RFQ","raw_text":"Nordlicht GmbH needs 1,000 ANC earbuds for Germany.","source_type":"TEXT"}).json()


def override(provider):
    async def dependency(): yield provider
    return dependency


def test_successful_extraction_persists_and_preserves_original(client):
    inquiry = create_inquiry(client)
    original = deepcopy(inquiry)
    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    first = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
    second = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
    assert first.status_code == 200
    assert first.json()["extraction_status"] == "SUCCESS"
    assert first.json()["extraction_id"] != second.json()["extraction_id"]
    detail = client.get(f'/api/v1/inquiries/{inquiry["id"]}').json()
    assert detail["raw_text"] == original["raw_text"]
    assert detail["revision"] == original["revision"]


def test_timeout_and_unavailable_are_classified_and_persisted(client):
    inquiry = create_inquiry(client)
    for code in (ProviderErrorCode.TIMEOUT, ProviderErrorCode.UNAVAILABLE):
        client.app.dependency_overrides[get_llm_provider] = override(FakeProvider(ProviderError(code, "failed", retryable=True)))
        response = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
        assert response.status_code == 200
        assert response.json()["extraction_status"] == "FAILED"
        assert response.json()["error_code"] == code.value


def test_human_owned_inquiry_fields_are_not_overwritten(client):
    inquiry = create_inquiry(client)
    before = client.get(f'/api/v1/inquiries/{inquiry["id"]}').json()
    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
    after = client.get(f'/api/v1/inquiries/{inquiry["id"]}').json()
    assert after["subject"] == before["subject"]
    assert after["extracted_fields"] == before["extracted_fields"]
    assert after["revision"] == before["revision"]


def test_latest_and_history_are_empty_before_first_extraction(client):
    inquiry = create_inquiry(client)

    latest = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions/latest')
    history = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions')

    assert latest.status_code == 200
    assert latest.json() is None
    assert history.status_code == 200
    assert history.json() == {"items": [], "total": 0}


def test_latest_and_history_include_failed_retry_records(client):
    inquiry = create_inquiry(client)
    client.app.dependency_overrides[get_llm_provider] = override(
        FakeProvider(ProviderError(ProviderErrorCode.TIMEOUT, "timed out", retryable=True))
    )
    failed = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
    assert failed.status_code == 200
    assert failed.json()["extraction_status"] == "FAILED"
    assert failed.json()["structured_data"] is None

    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    retried = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract')
    assert retried.status_code == 200
    assert retried.json()["extraction_status"] == "SUCCESS"

    latest = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions/latest')
    history = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions')
    record = client.get(
        f'/api/v1/inquiries/{inquiry["id"]}/extractions/{failed.json()["extraction_id"]}'
    )

    assert latest.json() == retried.json()
    assert history.json()["total"] == 2
    assert [item["extraction_status"] for item in history.json()["items"]] == ["SUCCESS", "FAILED"]
    assert history.json()["items"][0]["extraction_id"] == retried.json()["extraction_id"]
    assert record.json() == failed.json()


def test_extraction_reads_return_not_found_for_unknown_inquiry_or_record(client):
    missing_inquiry_id = "00000000-0000-0000-0000-000000000001"
    assert client.get(f"/api/v1/inquiries/{missing_inquiry_id}/extractions/latest").status_code == 404
    assert client.get(f"/api/v1/inquiries/{missing_inquiry_id}/extractions").status_code == 404

    inquiry = create_inquiry(client)
    missing_extraction_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(
        f'/api/v1/inquiries/{inquiry["id"]}/extractions/{missing_extraction_id}'
    )
    assert response.status_code == 404


def test_repeated_retries_are_all_readable_and_latest_failure_is_not_hidden(client):
    inquiry = create_inquiry(client)
    base = f'/api/v1/inquiries/{inquiry["id"]}'
    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    first = client.post(f'{base}/extract').json()
    second = client.post(f'{base}/extract').json()
    client.app.dependency_overrides[get_llm_provider] = override(
        FakeProvider(ProviderError(ProviderErrorCode.UNAVAILABLE, "unavailable", retryable=True))
    )
    failed = client.post(f'{base}/extract').json()

    # Reads must not instantiate or call a provider, including when no key is configured.
    def fail_if_provider_is_requested():
        raise AssertionError("Reading extraction history must not use the LLM provider")
    client.app.dependency_overrides[get_llm_provider] = fail_if_provider_is_requested
    assert client.get(f'{base}/extractions/latest').json() == failed
    history = client.get(f'{base}/extractions').json()
    assert history == {"items": [failed, second, first], "total": 3}
    assert len({item['extraction_id'] for item in history['items']}) == 3
    for item in history['items']:
        assert client.get(f'{base}/extractions/{item["extraction_id"]}').json() == item


def test_extraction_record_is_scoped_to_its_inquiry(client):
    inquiry = create_inquiry(client)
    other = client.post('/api/v1/inquiries', json={
        'subject': 'Another RFQ', 'raw_text': 'Another buyer requests a different product.', 'source_type': 'TEXT',
    }).json()
    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    record = client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract').json()
    response = client.get(f'/api/v1/inquiries/{other["id"]}/extractions/{record["extraction_id"]}')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'EXTRACTION_NOT_FOUND'
    assert client.get(f'/api/v1/inquiries/{other["id"]}/extractions').json() == {'items': [], 'total': 0}


def test_latest_and_history_have_identical_stable_order_when_timestamps_tie(client):
    from datetime import datetime, timezone
    from uuid import UUID
    from sqlalchemy import update
    from app.domains.extraction.models import InquiryExtractionRecord
    from tests.conftest import TestingSession

    inquiry = create_inquiry(client)
    client.app.dependency_overrides[get_llm_provider] = override(FakeProvider())
    records = [client.post(f'/api/v1/inquiries/{inquiry["id"]}/extract').json() for _ in range(3)]
    with TestingSession() as session:
        session.execute(update(InquiryExtractionRecord).where(
            InquiryExtractionRecord.inquiry_id == UUID(inquiry['id'])
        ).values(created_at=datetime(2026, 11, 18, tzinfo=timezone.utc)))
        session.commit()
    expected_ids = sorted((item['extraction_id'] for item in records), reverse=True)
    history = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions').json()
    latest = client.get(f'/api/v1/inquiries/{inquiry["id"]}/extractions/latest').json()
    assert [item['extraction_id'] for item in history['items']] == expected_ids
    assert latest == history['items'][0]
