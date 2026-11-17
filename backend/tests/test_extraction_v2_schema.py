import pytest
from pydantic import ValidationError

from app.domains.extraction.v2_schemas import StructuredInquiryExtraction


def valid_payload():
    field = lambda value=None, status="INSUFFICIENT_DATA", evidence=None: {"value": value, "status": status, "evidence": evidence}
    return {
        "customer": {"customer_name": field(), "company_name": field("Nordlicht GmbH", "CONFIRMED", "Nordlicht GmbH"), "email": field(), "country": field("Germany", "CONFIRMED", "Germany")},
        "products": [{"product_type": field("ANC earbuds", "CONFIRMED", "ANC earbuds"), "product_description": field("ANC wireless earbuds", "CONFIRMED", "ANC wireless earbuds"), "quantity": field(1000, "CONFIRMED", "1,000"), "quantity_unit": field("units", "CONFIRMED", "units"), "specifications": field({"feature":"ANC"}, "CONFIRMED", "ANC"), "customization_requirements": field(["OEM logo"], "CONFIRMED", "OEM logo"), "certification_requirements": field()}],
        "business": {"target_market": field("Germany", "CONFIRMED", "Germany"), "expected_delivery": field(), "target_price": field(), "purchasing_intent": field("Request for quotation", "INFERRED", "need 1,000")},
        "missing_fields": ["expected_delivery"],
        "clarification_questions": ["What is your expected delivery date?"],
    }


def test_v2_schema_accepts_multiple_products_and_statuses():
    payload = valid_payload()
    payload["products"].append(payload["products"][0] | {"product_type": {"value":"charging case", "status":"CONFIRMED", "evidence":"charging case"}})
    result = StructuredInquiryExtraction.model_validate(payload)
    assert len(result.products) == 2
    assert result.products[0].quantity.value == 1000


def test_null_value_is_normalized_to_insufficient_data():
    payload = valid_payload()
    payload["customer"]["email"] = {"value": None, "status": "CONFIRMED", "evidence": "invented"}
    result = StructuredInquiryExtraction.model_validate(payload)
    assert result.customer.email.status.value == "INSUFFICIENT_DATA"
    assert result.customer.email.evidence is None


def test_unknown_fields_are_rejected():
    payload = valid_payload()
    payload["invented"] = "no"
    with pytest.raises(ValidationError):
        StructuredInquiryExtraction.model_validate(payload)
