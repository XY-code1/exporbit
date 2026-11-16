"""Extraction schema validation and status coercion tests."""
import pytest
from pydantic import ValidationError

from app.domains.extraction.schemas import ExtractedField, InfoStatus, InquiryExtraction

VALID_JSON = """{
  "fields": {
    "customer_need": {"value": "无线蓝牙耳机", "status": "CONFIRMED", "evidence": "采购 500 副"},
    "quantity": {"value": "500 副", "status": "CONFIRMED", "evidence": "500 副"},
    "target_market": {"value": "德国", "status": "CONFIRMED", "evidence": "发到德国"},
    "customization_needs": {"value": null, "status": "INSUFFICIENT_DATA", "evidence": null},
    "delivery_timeline": {"value": null, "status": "INSUFFICIENT_DATA", "evidence": null},
    "price_terms": {"value": null, "status": "INSUFFICIENT_DATA", "evidence": null}
  }
}
"""


def test_full_valid_parse():
    extraction = InquiryExtraction.model_validate_json(VALID_JSON)
    assert extraction.customer_need.value == "无线蓝牙耳机"
    assert extraction.customer_need.status is InfoStatus.CONFIRMED
    assert extraction.quantity.value == "500 副"
    assert extraction.customization_needs.value is None
    assert extraction.customization_needs.status is InfoStatus.INSUFFICIENT_DATA


def test_null_value_coerces_status_to_insufficient_data():
    field = ExtractedField(value=None, status=InfoStatus.CONFIRMED, evidence="引用")
    assert field.status is InfoStatus.INSUFFICIENT_DATA
    assert field.evidence is None


def test_present_value_with_absent_status_coerces_to_needs_confirmation():
    field = ExtractedField(value="500", status=InfoStatus.INSUFFICIENT_DATA)
    assert field.status is InfoStatus.NEEDS_CONFIRMATION


def test_numeric_value_is_stringified():
    field = ExtractedField(value=500, status=InfoStatus.CONFIRMED)
    assert field.value == "500"


def test_missing_field_raises_validation_error():
    with pytest.raises(ValidationError):
        InquiryExtraction.model_validate_json('{"fields": {"customer_need": {"value": "x", "status": "CONFIRMED"}}}')


def test_extra_field_is_rejected():
    payload = VALID_JSON.replace('"fields": {', '"fields": {"extra": {"value": "x", "status": "CONFIRMED"}, ')
    with pytest.raises(ValidationError):
        InquiryExtraction.model_validate_json(payload)


def test_as_persisted_dict_shape():
    extraction = InquiryExtraction.model_validate_json(VALID_JSON)
    persisted = extraction.as_persisted_dict()
    assert set(persisted) == {
        "customer_need",
        "quantity",
        "target_market",
        "customization_needs",
        "delivery_timeline",
        "price_terms",
    }
    assert persisted["quantity"]["status"] == "CONFIRMED"
