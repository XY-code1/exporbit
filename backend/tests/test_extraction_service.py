"""Extraction service tests: human-edit precedence and input hashing."""
from app.domains.extraction.schemas import ExtractedField, InfoStatus, InquiryExtraction
from app.domains.extraction.service import input_hash, merge_extraction


def _extraction(**overrides) -> InquiryExtraction:
    fields = {
        "customer_need": ExtractedField(value="无线耳机", status=InfoStatus.CONFIRMED, evidence="耳机"),
        "quantity": ExtractedField(value="500 副", status=InfoStatus.CONFIRMED, evidence="500 副"),
        "target_market": ExtractedField(value="德国", status=InfoStatus.CONFIRMED, evidence="德国"),
        "customization_needs": ExtractedField(value=None, status=InfoStatus.INSUFFICIENT_DATA),
        "delivery_timeline": ExtractedField(value=None, status=InfoStatus.INSUFFICIENT_DATA),
        "price_terms": ExtractedField(value=None, status=InfoStatus.INSUFFICIENT_DATA),
    }
    fields.update(overrides)
    return InquiryExtraction(**fields)


def test_input_hash_is_deterministic_and_sensitive_to_content():
    assert input_hash("询盘内容 A") == input_hash("询盘内容 A")
    assert input_hash(" 询盘内容 A ") == input_hash("询盘内容 A")
    assert input_hash("询盘内容 A") != input_hash("询盘内容 B")


def test_missing_fields_are_filled():
    existing = {}
    merged, changed = merge_extraction(existing, _extraction())
    assert changed is True
    assert merged["quantity"]["value"] == "500 副"
    assert merged["target_market"]["status"] == "CONFIRMED"


def test_human_confirmed_fields_are_never_overwritten():
    existing = {
        "quantity": {"value": "800 副", "status": "CONFIRMED", "evidence": "人工核实"},
        "target_market": {"value": "波兰", "status": "INFERRED", "evidence": "人工推断"},
    }
    merged, changed = merge_extraction(existing, _extraction())
    assert merged["quantity"]["value"] == "800 副"
    assert merged["target_market"]["value"] == "波兰"
    # customer_need etc. were missing and got filled
    assert merged["customer_need"]["value"] == "无线耳机"
    assert changed is True


def test_needs_confirmation_fields_may_be_refreshed_by_ai_rerun():
    existing = {"quantity": {"value": "旧值", "status": "NEEDS_CONFIRMATION", "evidence": None}}
    merged, changed = merge_extraction(existing, _extraction())
    assert merged["quantity"]["value"] == "500 副"
    assert changed is True


def test_identical_proposal_does_not_report_change():
    existing = {
        "customer_need": {"value": "无线耳机", "status": "CONFIRMED", "evidence": "耳机"},
        "quantity": {"value": "500 副", "status": "CONFIRMED", "evidence": "500 副"},
        "target_market": {"value": "德国", "status": "CONFIRMED", "evidence": "德国"},
        "customization_needs": {"value": None, "status": "INSUFFICIENT_DATA", "evidence": None},
        "delivery_timeline": {"value": None, "status": "INSUFFICIENT_DATA", "evidence": None},
        "price_terms": {"value": None, "status": "INSUFFICIENT_DATA", "evidence": None},
    }
    merged, changed = merge_extraction(existing, _extraction())
    assert changed is False
    assert merged == existing


def test_unknown_persisted_keys_are_preserved():
    existing = {"custom_note": "人工备注", "quantity": {"value": "1 副", "status": "CONFIRMED"}}
    merged, changed = merge_extraction(existing, _extraction())
    assert merged["custom_note"] == "人工备注"
    assert merged["quantity"]["value"] == "1 副"
