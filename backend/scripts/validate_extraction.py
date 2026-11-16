"""POC-02 validation harness: structured extraction against the live DeepSeek API.

Runs the fixed synthetic corpus through `ExtractionService`, records one
`llm_runs` row per call (PostgreSQL, or in-memory when the database is
unavailable / --no-db), computes schema pass rate, per-field F1, token/latency
statistics and error classification, then writes outputs/POC_02_RESULTS.json
and outputs/POC_02_VALIDATION_REPORT.md.

Usage (from backend/):  ../.venv/Scripts/python.exe scripts/validate_extraction.py [--no-db]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.domains.extraction.evaluation import ALL_FIELDS, aggregate, evaluate_item  # noqa: E402
from app.domains.extraction.service import ExtractionService  # noqa: E402
from app.domains.inquiry.models import Customer, Inquiry  # noqa: E402,F401  (register FK target tables)
from app.domains.llm_run.models import LLMRun  # noqa: E402
from app.domains.llm_run.repository import LLMRunRepository  # noqa: E402
from app.infrastructure.database import SessionLocal  # noqa: E402
from app.providers.deepseek import DeepSeekProvider  # noqa: E402

CORPUS_PATH = BACKEND_DIR / "data" / "poc02_corpus.json"
RESULTS_PATH = PROJECT_DIR / "outputs" / "POC_02_RESULTS.json"
REPORT_PATH = PROJECT_DIR / "outputs" / "POC_02_VALIDATION_REPORT.md"
POLITENESS_DELAY_SECONDS = 0.5

SCHEMA_PASS_RATE_TARGET = 0.90
KEY_F1_TARGET = 0.85


class _InMemoryRunRepository:
    """Fallback recorder used when PostgreSQL is unavailable."""

    def __init__(self) -> None:
        self.runs: list[LLMRun] = []

    def add(self, run: LLMRun) -> LLMRun:
        self.runs.append(run)
        return run


def _percent(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def _avg(values: list[int]) -> int:
    return round(sum(values) / len(values)) if values else 0


async def run_validation(use_db: bool) -> tuple[dict, list[dict]]:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    items = corpus["items"]
    provider = DeepSeekProvider()
    session = None
    runs_persisted = False
    if use_db:
        try:
            session = SessionLocal()
            session.execute(text("SELECT 1"))
            repo = LLMRunRepository(session)
            runs_persisted = True
        except Exception as exc:
            print(f"[warn] PostgreSQL 不可用，llm_runs 仅在内存记录: {type(exc).__name__}", flush=True)
            if session is not None:
                session.close()
            session = None
            repo = _InMemoryRunRepository()
    else:
        repo = _InMemoryRunRepository()
    per_item: list[dict] = []
    error_counts: dict[str, int] = {}
    persist_failures = 0
    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    latencies: list[int] = []
    started_at = datetime.now(timezone.utc)
    try:
        service = ExtractionService(provider, repo)
        for index, item in enumerate(items, start=1):
            extraction = None
            record: dict = {
                "id": item["id"],
                "language": item["language"],
                "ok": False,
                "repair_used": False,
                "attempts": 0,
                "error_code": None,
            }
            try:
                outcome = await service.extract(inquiry_text=item["raw_text"])
                extraction = outcome.extraction
                record.update(
                    {
                        "ok": outcome.extraction is not None,
                        "repair_used": outcome.run.repair_used,
                        "attempts": outcome.run.attempts,
                        "error_code": outcome.error_code,
                        "latency_ms": outcome.run.latency_ms,
                        "prompt_tokens": outcome.run.prompt_tokens,
                        "completion_tokens": outcome.run.completion_tokens,
                        "total_tokens": outcome.run.total_tokens,
                        "input_hash": outcome.run.input_hash,
                        "run_id": str(outcome.run.id),
                    }
                )
                if outcome.run.status == "SUCCESS":
                    total_tokens["prompt"] += outcome.run.prompt_tokens
                    total_tokens["completion"] += outcome.run.completion_tokens
                    total_tokens["total"] += outcome.run.total_tokens
                    latencies.append(outcome.run.latency_ms)
                if outcome.error_code:
                    error_counts[outcome.error_code] = error_counts.get(outcome.error_code, 0) + 1
            except Exception as exc:  # harness must survive unexpected failures
                error_code = "UNEXPECTED"
                record["error_code"] = error_code
                record["error_type"] = type(exc).__name__
                error_counts[error_code] = error_counts.get(error_code, 0) + 1
            predicted = (
                {name: extraction.field(name).value for name in ALL_FIELDS} if extraction
                else {name: None for name in ALL_FIELDS}
            )
            record["extracted"] = predicted
            record["golden"] = item["golden"]
            record["scores"] = evaluate_item(item["golden"], predicted)
            record["persisted"] = None
            per_item.append(record)
            if session is not None:
                try:
                    session.commit()
                    record["persisted"] = True
                except Exception as exc:  # keep the harness alive; audit gap is reported
                    session.rollback()
                    persist_failures += 1
                    record["persisted"] = False
                    print(f"[warn] {item['id']} llm_runs 持久化失败: {type(exc).__name__}", flush=True)
            print(f"[{index}/{len(items)}] {item['id']} {'OK' if record['ok'] else record['error_code']}", flush=True)
            if index < len(items):
                await asyncio.sleep(POLITENESS_DELAY_SECONDS)
    finally:
        await provider.close()
        if session is not None:
            session.close()

    n = len(per_item)
    successful = sum(1 for record in per_item if record["ok"])
    repaired = sum(1 for record in per_item if record["ok"] and record["repair_used"])
    invalid_output_count = error_counts.get("PROVIDER_INVALID_OUTPUT", 0)
    metrics = aggregate([record["scores"] for record in per_item], n)
    language_counts: dict[str, int] = {}
    for item in items:
        language_counts[item["language"]] = language_counts.get(item["language"], 0) + 1

    schema_pass_rate = successful / n
    key_f1 = metrics["key_fields_macro_f1"]
    schema_ok = schema_pass_rate >= SCHEMA_PASS_RATE_TARGET
    f1_ok = key_f1 >= KEY_F1_TARGET

    summary = {
        "corpus": {"file": "backend/data/poc02_corpus.json", "items": n, "languages": language_counts},
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "model": provider._model,
        "runs_persisted": runs_persisted,
        "persistence_failures": persist_failures,
        "schema": {
            "valid_responses": successful,
            "schema_pass_rate": round(schema_pass_rate, 4),
            "first_attempt_valid": successful - repaired,
            "first_attempt_pass_rate": round((successful - repaired) / n, 4),
            "repair_used": repaired,
            "repair_success_rate": round(repaired / (repaired + invalid_output_count), 4)
            if (repaired + invalid_output_count)
            else None,
        },
        "metrics": metrics,
        "tokens": total_tokens,
        "latency_ms": {"count": len(latencies), "avg": _avg(latencies), "min": min(latencies) if latencies else 0, "max": max(latencies) if latencies else 0},
        "error_classification": error_counts,
        "verdict": {
            "result": "PASS" if (schema_ok and f1_ok) else "FAIL",
            "criteria": {
                "schema_pass_rate": {"value": round(schema_pass_rate, 4), "target": SCHEMA_PASS_RATE_TARGET, "passed": schema_ok},
                "key_fields_macro_f1": {"value": key_f1, "target": KEY_F1_TARGET, "passed": f1_ok},
            },
        },
    }
    return summary, per_item


def _fmt(value: object) -> str:
    return "—" if value is None else str(value)


def _mismatches(per_item: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in per_item:
        for name in ALL_FIELDS:
            score = record["scores"].get(name, {})
            if score.get("fp") or score.get("fn"):
                rows.append(
                    {
                        "id": record["id"],
                        "field": name,
                        "extracted": record["extracted"].get(name),
                        "golden": record["golden"].get(name),
                        "fp": score.get("fp", 0),
                        "fn": score.get("fn", 0),
                    }
                )
    return rows


def build_report(summary: dict, per_item: list[dict]) -> str:
    schema = summary["schema"]
    metrics = summary["metrics"]["per_field"]
    errors = summary["error_classification"]
    failed = [record for record in per_item if not record["ok"]]
    repaired = [record for record in per_item if record["ok"] and record["repair_used"]]
    mismatches = _mismatches(per_item)

    lines: list[str] = []
    lines.append("# Exporbit POC-02 验证报告：DeepSeek 结构化抽取")
    lines.append("")
    lines.append(f"- 验证时间（UTC）：{summary['started_at']} ~ {summary['finished_at']}")
    lines.append(f"- 语料：{summary['corpus']['file']}（{summary['corpus']['items']} 条合成询盘，中文 {summary['corpus']['languages'].get('CN', 0)} / 英文 {summary['corpus']['languages'].get('EN', 0)}；不含任何真实客户数据）")
    lines.append(f"- 模型：`{summary['model']}`（JSON 输出模式，temperature=0，max_tokens=1500）")
    persistence_note = "已写入 PostgreSQL"
    if not summary["runs_persisted"]:
        persistence_note = "**未持久化（PostgreSQL 不可用，仅内存记录）**"
    elif summary.get("persistence_failures"):
        persistence_note = f"已写入 PostgreSQL（{summary['persistence_failures']} 条持久化失败）"
    lines.append(f"- llm_runs 持久化：{persistence_note}")
    lines.append(f"- 结论：**{summary['verdict']['result']}**")
    lines.append("")

    section_no = 0

    def heading(title: str) -> None:
        nonlocal section_no
        section_no += 1
        lines.append(f"## {section_no}. {title}")
        lines.append("")

    heading("成功标准")
    lines.append("| 标准 | 目标 | 实测 | 通过 |")
    lines.append("|---|---|---|---|")
    schema_row = summary["verdict"]["criteria"]["schema_pass_rate"]
    f1_row = summary["verdict"]["criteria"]["key_fields_macro_f1"]
    lines.append(f"| 响应通过 schema 校验 | ≥ {SCHEMA_PASS_RATE_TARGET:.0%} | {schema_row['value']:.1%} | {'✅' if schema_row['passed'] else '❌'} |")
    lines.append(f"| 关键字段 F1（macro） | ≥ {KEY_F1_TARGET} | {f1_row['value']} | {'✅' if f1_row['passed'] else '❌'} |")
    lines.append("")
    heading("Schema 通过与修复")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 最终有效响应 | {schema['valid_responses']}/{summary['corpus']['items']}（{schema['schema_pass_rate']:.1%}） |")
    lines.append(f"| 首次请求即通过 | {schema['first_attempt_valid']}（{schema['first_attempt_pass_rate']:.1%}） |")
    lines.append(f"| 触发一次修复请求并成功 | {schema['repair_used']} |")
    lines.append(f"| 修复成功率 | {schema['repair_success_rate'] if schema['repair_success_rate'] is not None else 'N/A'} |")
    lines.append("")
    heading("字段级 F1（golden 精确匹配 + 缺省检测）")
    lines.append("| 字段 | Precision | Recall | F1 | 存在性准确率 |")
    lines.append("|---|---|---|---|---|")
    for name in ALL_FIELDS:
        row = metrics[name]
        lines.append(f"| {name} | {row['precision']} | {row['recall']} | {row['f1']} | {row['presence_accuracy']:.1%} |")
    lines.append(f"| **关键字段 macro F1** | | | **{summary['metrics']['key_fields_macro_f1']}** | |")
    lines.append(f"| **全部字段 macro F1** | | | **{summary['metrics']['all_fields_macro_f1']}** | |")
    lines.append("")
    lines.append("> 方法论：golden 标注为期望抽取值（null=原文未提及）。预测值与 golden 归一化（去空白/大小写/尾标点）后精确相等或同为 null 计正确；golden 为 null 而预测有值计 FP（幻觉）；golden 有值而预测为 null 计 FN（漏抽）；两者均非空但不相等，同一字段同时计 FP 与 FN。status 标签（CONFIRMED/INFERRED）属主观判断，不参与评分。")
    lines.append("")
    heading("用量与延迟（仅成功调用）")
    lines.append(f"- 输入 token：{summary['tokens']['prompt']}；输出 token：{summary['tokens']['completion']}；合计：{summary['tokens']['total']}")
    lines.append(f"- 平均 token/条：{_avg([record.get('total_tokens', 0) for record in per_item if record['ok']])}")
    lines.append(f"- 延迟：平均 {summary['latency_ms']['avg']} ms，最小 {summary['latency_ms']['min']} ms，最大 {summary['latency_ms']['max']} ms（{summary['latency_ms']['count']} 次成功调用）")
    lines.append("")
    heading("错误分类")
    if errors:
        lines.append("| 错误码 | 次数 |")
        lines.append("|---|---|")
        for code, count in sorted(errors.items()):
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("无失败调用。")
    lines.append("")
    if mismatches:
        heading("字段级差异明细（预测 vs golden）")
        lines.append(f"共 {len(mismatches)} 处字段级差异。")
        lines.append("")
        lines.append("| 语料 ID | 字段 | 预测值 | golden |")
        lines.append("|---|---|---|---|")
        for row in mismatches:
            lines.append(f"| {row['id']} | {row['field']} | {_fmt(row['extracted'])} | {_fmt(row['golden'])} |")
        lines.append("")
        cjk = re.compile(r"[\u4e00-\u9fff]")
        language_mix = [
            f"{record['id']}.{name}"
            for record in per_item
            if record.get("language") == "EN"
            for name in ALL_FIELDS
            if isinstance(record["extracted"].get(name), str) and cjk.search(record["extracted"][name])
        ]
        if language_mix:
            lines.append(
                f"- 输出语言未跟随输入语言：{len(language_mix)} 处（{', '.join(language_mix)}），英文询盘返回了中文值。这是真实质量问题，建议在 system prompt 增加输出语言跟随输入语言的约束。"
            )
            lines.append("")
        lines.append("- 其余差异多为同义改写或粒度差异（预测带出原文修饰语、golden 更简略），内容大多无害，但按精确匹配计为不一致。")
        lines.append("")
    if failed:
        heading("失败明细")
        lines.append("| 语料 ID | 错误码 | attempts |")
        lines.append("|---|---|---|")
        for record in failed:
            lines.append(f"| {record['id']} | {record.get('error_code')} | {record.get('attempts')} |")
        lines.append("")
    if repaired:
        heading("触发修复的条目")
        lines.append("| 语料 ID | attempts |")
        lines.append("|---|---|")
        for record in repaired:
            lines.append(f"| {record['id']} | {record.get('attempts')} |")
        lines.append("")
    heading("边界与限制")
    lines.append("- 本 POC 仅验证 Provider 接口 + DeepSeek Adapter + 抽取 schema 的线上可用性，未接入 /inquiries 业务路径（按 POC-02 范围约定）。")
    lines.append("- 每轮调用均写入 `llm_runs` 表（purpose/model/token/延迟/输入哈希/错误码），原文不落库。")
    lines.append("- 人工字段保护（CONFIRMED/INFERRED 不被 AI 重跑覆盖）由单元测试 `test_extraction_service.py` 验证，属纯函数行为演示，待 POC-03 接入业务路径后做端到端验证。")
    lines.append("- 语料为合成数据；真实询盘的领域分布、噪音与语言混杂会带来偏差。")
    lines.append("- 逐条明细见 `outputs/POC_02_RESULTS.json`。")
    lines.append("")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="POC-02 DeepSeek 结构化抽取线上验证")
    parser.add_argument("--no-db", action="store_true", help="不连接 PostgreSQL；llm_runs 仅在内存记录")
    parser.add_argument("--report-only", action="store_true", help="不调用 API；从既有 outputs/POC_02_RESULTS.json 重新生成报告")
    args = parser.parse_args()
    if args.report_only:
        payload = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        summary, per_item = payload["summary"], payload["items"]
    else:
        summary, per_item = await run_validation(use_db=not args.no_db)
        RESULTS_PATH.write_text(json.dumps({"summary": summary, "items": per_item}, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, per_item), encoding="utf-8")
    print("\n=== POC-02 验证完成 ===")
    print(f"schema 通过率: {summary['schema']['schema_pass_rate']:.1%}（目标 ≥ {SCHEMA_PASS_RATE_TARGET:.0%}）")
    print(f"关键字段 macro F1: {summary['metrics']['key_fields_macro_f1']}（目标 ≥ {KEY_F1_TARGET}）")
    print(f"结论: {summary['verdict']['result']}")
    print(f"错误分类: {summary['error_classification'] or '无'}")
    print(f"报告: {REPORT_PATH}")
    print(f"明细: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
