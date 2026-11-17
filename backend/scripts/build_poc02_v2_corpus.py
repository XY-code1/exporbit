"""Build the fixed, human-authored POC-02 V2 evaluation corpus.

This utility is deterministic and never calls an LLM.  The first 24 labels are
transcribed from the reviewed legacy corpus; six cases cover V2-only shapes.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
legacy = json.loads((ROOT / "data/poc02_corpus.json").read_text(encoding="utf-8"))["items"]


def field(value):
    return {"value": value, "status": "CONFIRMED" if value is not None else "INSUFFICIENT_DATA", "evidence": None}


def convert(item):
    g = item["golden"]
    product = {
        "product_type": field(g["customer_need"]),
        "product_description": field(None),
        "quantity": field(None),
        "quantity_unit": field(None),
        "specifications": field({}),
        "customization_requirements": field([g["customization_needs"]] if g["customization_needs"] else []),
        "certification_requirements": field([]),
    }
    return {
        "id": item["id"], "language": item["language"], "category": "reviewed_legacy",
        "raw_text": item["raw_text"],
        "expected": {
            "customer": {k: field(None) for k in ("customer_name", "company_name", "email", "country")},
            "products": [product],
            "business": {
                "target_market": field(g["target_market"]), "expected_delivery": field(g["delivery_timeline"]),
                "target_price": field(g["price_terms"]), "purchasing_intent": field(None),
            },
        },
    }


items = [convert(x) for x in legacy]
extras = [
    ("V2-25", "EN", "multiple_products", "I am Anna from Nordlicht GmbH, anna@nordlicht.de. We need 500 ANC earbuds with our logo and 200 Bluetooth speakers, delivery to Germany in September. CE compliance required."),
    ("V2-26", "CN-EN", "mixed_language", "Hi，我们公司 BluePeak 想采购 smart watches，数量大概 1k 左右，target market 是 France，能做 private label 吗？"),
    ("V2-27", "EN", "non_standard_english", "need earbud maybe 2-3k pcs, ship europe, cert maybe CE? price pls. trial first not sure."),
    ("V2-28", "CN", "missing_country", "我们需要 300 台支持 Wi-Fi 6 的智能网关，贴牌包装，六周内交货。"),
    ("V2-29", "EN", "ambiguous_quantity", "Please quote solar security cameras. Initial order could be several cartons; quantity to be confirmed after samples."),
    ("V2-30", "EN", "unclear_intent", "Do you have RoHS or CE for wireless chargers? I am researching options and have no purchase plan yet."),
]
for ident, lang, category, raw in extras:
    items.append({"id": ident, "language": lang, "category": category, "raw_text": raw, "expected": None})

# Explicit reviewed labels for V2-only cases.  Null denotes unavailable—not a guess.
labels = {
"V2-25": (["ANC earbuds", "Bluetooth speakers"], "Germany", "September"),
"V2-26": (["smart watches"], "France", None),
"V2-27": (["earbud"], "Europe", None),
"V2-28": (["智能网关"], None, "六周内"),
"V2-29": (["solar security cameras"], None, None),
"V2-30": (["wireless chargers"], None, None),
}
for item in items[-6:]:
    products, market, delivery = labels[item["id"]]
    item["expected"] = {
        "customer": {k: field(None) for k in ("customer_name", "company_name", "email", "country")},
        "products": [{"product_type": field(p), "product_description": field(None), "quantity": field(None),
            "quantity_unit": field(None), "specifications": field({}), "customization_requirements": field([]),
            "certification_requirements": field([])} for p in products],
        "business": {"target_market": field(market), "expected_delivery": field(delivery),
            "target_price": field(None), "purchasing_intent": field(None)},
    }

out = {"metadata": {"kind": "synthetic", "labeling": "human-authored; deterministic; no model grading", "count": 30}, "items": items}
(ROOT / "data/poc02_v2_corpus.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote 30 cases")
