"""Evaluation helper tests: normalization, confusion counting, aggregation."""
from app.domains.extraction.evaluation import (
    ALL_FIELDS,
    aggregate,
    evaluate_item,
    field_confusion,
    normalize,
)


def test_normalize_strips_whitespace_case_and_trailing_punctuation():
    assert normalize("  FOB Shenzhen  ") == "fobshenzhen"
    assert normalize("500 副。") == "500副"
    assert normalize("Germany.") == "germany"
    assert normalize(None) is None
    assert normalize("   ") is None


def test_field_confusion_cases():
    assert field_confusion(None, None) == (1, 0, 0)
    assert field_confusion(None, "德国") == (0, 1, 0)  # hallucination
    assert field_confusion("德国", None) == (0, 0, 1)  # miss
    assert field_confusion("德国", " 德国 ") == (1, 0, 0)
    assert field_confusion("德国", "法国") == (0, 1, 1)  # wrong value counts both


def test_evaluate_item_shape():
    golden = {"customer_need": "耳机", "quantity": None}
    predicted = {"customer_need": "耳机", "quantity": "500"}
    scores = evaluate_item(golden, predicted)
    assert scores["customer_need"]["tp"] == 1
    assert scores["quantity"]["fp"] == 1
    assert set(scores) == set(golden)


def test_aggregate_macro_f1():
    golden = {
        "customer_need": "耳机",
        "quantity": None,
        "target_market": "德国",
        "customization_needs": None,
        "delivery_timeline": None,
        "price_terms": None,
    }
    per_item = [evaluate_item(golden, golden), evaluate_item(golden, golden)]
    summary = aggregate(per_item, item_count=2)
    assert summary["key_fields_macro_f1"] == 1.0
    assert summary["all_fields_macro_f1"] == 1.0
    assert summary["per_field"]["quantity"]["presence_accuracy"] == 1.0
    assert set(summary["per_field"]) == set(ALL_FIELDS)
    for name in ALL_FIELDS:
        assert summary["per_field"][name]["f1"] == 1.0
