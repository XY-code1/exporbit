"""Evaluation helpers for the extraction POC: normalization and per-field F1.

Methodology: golden labels hold the expected extracted value per field (null
when the field is absent from the inquiry). A prediction is correct when both
golden and predicted values normalize equal, or both are null (absence
detection). A predicted value where golden is null counts as a false positive
(hallucination); a null prediction where golden has a value counts as a false
negative (miss). Status labels (CONFIRMED vs INFERRED) are not scored because
that judgement is inherently subjective; value-level F1 is the acceptance
criterion.
"""
from __future__ import annotations

import re

KEY_FIELDS = ("customer_need", "quantity", "target_market", "customization_needs")
SECONDARY_FIELDS = ("delivery_timeline", "price_terms")
ALL_FIELDS = KEY_FIELDS + SECONDARY_FIELDS

_TRAILING_PUNCT = ".,;:!?。；：，、\"'"


def normalize(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().lower()
    text = re.sub(r"\s+", "", text)
    text = text.rstrip(_TRAILING_PUNCT)
    return text or None


def field_confusion(golden: str | None, predicted: str | None) -> tuple[int, int, int]:
    """Return (tp, fp, fn) for one field of one item."""
    golden_norm = normalize(golden)
    predicted_norm = normalize(predicted)
    if golden_norm is None and predicted_norm is None:
        return 1, 0, 0
    if golden_norm is None:
        return 0, 1, 0
    if predicted_norm is None:
        return 0, 0, 1
    if golden_norm == predicted_norm:
        return 1, 0, 0
    return 0, 1, 1


def _precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if (tp + fp) else 0.0


def _recall(tp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def evaluate_item(golden: dict[str, str | None], predicted: dict[str, str | None]) -> dict[str, dict]:
    """Per-field confusion and scores for one corpus item."""
    per_field: dict[str, dict] = {}
    for name in golden:
        tp, fp, fn = field_confusion(golden.get(name), predicted.get(name))
        precision = _precision(tp, fp)
        recall = _recall(tp, fn)
        per_field[name] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(_f1(precision, recall), 4),
        }
    return per_field


def aggregate(per_item: list[dict[str, dict]], item_count: int) -> dict:
    """Aggregate per-item confusion into per-field metrics plus overall scores."""
    totals: dict[str, dict] = {name: {"tp": 0, "fp": 0, "fn": 0} for name in ALL_FIELDS}
    for item_scores in per_item:
        for name, scores in item_scores.items():
            if name in totals:
                totals[name]["tp"] += scores["tp"]
                totals[name]["fp"] += scores["fp"]
                totals[name]["fn"] += scores["fn"]
    metrics: dict[str, dict] = {}
    for name in ALL_FIELDS:
        tp, fp, fn = totals[name]["tp"], totals[name]["fp"], totals[name]["fn"]
        precision = _precision(tp, fp)
        recall = _recall(tp, fn)
        metrics[name] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(_f1(precision, recall), 4),
            # tp counts both correct-absence and correct-value decisions
            "presence_accuracy": round(tp / item_count, 4) if item_count else 0.0,
        }
    key_f1 = sum(metrics[name]["f1"] for name in KEY_FIELDS) / len(KEY_FIELDS)
    all_f1 = sum(metrics[name]["f1"] for name in ALL_FIELDS) / len(ALL_FIELDS)
    return {"per_field": metrics, "key_fields_macro_f1": round(key_f1, 4), "all_fields_macro_f1": round(all_f1, 4)}
