from copy import deepcopy

from app.api.inquiries import get_llm_provider
from app.domains.extraction.v2_schemas import StructuredInquiryExtraction
from app.providers.contracts import LLMResult, LLMUsage, ProviderError, ProviderErrorCode
from tests.test_extraction_v2_schema import valid_payload


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
