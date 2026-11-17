"""Run the 30-case, independently labelled POC-02 V2 corpus against DeepSeek."""
from __future__ import annotations

import asyncio, json, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.domains.extraction.v2_prompt import EXTRACTION_V2_PROMPT
from app.domains.extraction.v2_schemas import StructuredInquiryExtraction
from app.providers.contracts import Message, MessageRole
from app.providers.deepseek import DeepSeekProvider


def norm(value):
    if value is None: return None
    if isinstance(value, str): return " ".join(value.lower().split())
    return value


async def main():
    corpus = json.loads((BACKEND / "data/poc02_v2_corpus.json").read_text(encoding="utf-8"))
    provider = DeepSeekProvider()
    rows, scores = [], defaultdict(lambda: [0, 0])
    started = datetime.now(timezone.utc).isoformat()
    try:
        for n, item in enumerate(corpus["items"], 1):
            row = {"id": item["id"], "ok": False}
            try:
                result = await provider.generate_structured(
                    purpose="poc02_v2_evaluation",
                    messages=[Message(role=MessageRole.SYSTEM, content=EXTRACTION_V2_PROMPT), Message(role=MessageRole.USER, content=item["raw_text"])],
                    output_schema=StructuredInquiryExtraction, temperature=0, max_tokens=3000,
                )
                got, exp = result.data, item["expected"]
                checks = {
                    "product_type": ([norm(x.product_type.value) for x in got.products], [norm(x["product_type"]["value"]) for x in exp["products"]]),
                    "target_market": (norm(got.business.target_market.value), norm(exp["business"]["target_market"]["value"])),
                    "expected_delivery": (norm(got.business.expected_delivery.value), norm(exp["business"]["expected_delivery"]["value"])),
                }
                for name, (actual, expected) in checks.items():
                    scores[name][1] += 1
                    if actual == expected: scores[name][0] += 1
                row.update(ok=True, checks={k: {"actual": a, "expected": e, "match": a == e} for k, (a,e) in checks.items()}, attempts=result.attempts, repair_used=result.repair_used, latency_ms=result.latency_ms)
            except Exception as exc:
                row.update(error_type=type(exc).__name__, error=str(exc))
                print(f"  {type(exc).__name__}: {exc} {getattr(exc, 'details', None)}", flush=True)
            rows.append(row)
            print(f"[{n}/30] {item['id']} {'OK' if row['ok'] else 'FAIL'}", flush=True)
    finally:
        await provider.close()
    summary = {
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "backend/data/poc02_v2_corpus.json", "cases": len(rows),
        "schema_success_rate": sum(r["ok"] for r in rows) / len(rows),
        "field_accuracy": {k: {"correct": v[0], "total": v[1], "accuracy": v[0]/v[1] if v[1] else 0} for k,v in scores.items()},
        "rows": rows,
    }
    out = ROOT / "outputs/POC_02_V2_RESULTS.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)

if __name__ == "__main__": asyncio.run(main())
