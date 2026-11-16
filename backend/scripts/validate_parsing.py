"""POC-03 harness: parse the synthetic corpus, check expectations, write report.

Usage (from backend/): ../.venv/Scripts/python.exe scripts/validate_parsing.py
Outputs: outputs/POC_03_RESULTS.json and outputs/POC_03_VALIDATION_REPORT.md
"""
from __future__ import annotations

import importlib.metadata as metadata
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
CORPUS_DIR = BACKEND_DIR / "data" / "poc03_corpus"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
sys.path.insert(0, str(BACKEND_DIR))

from app.providers.documents import ParseError, parse_document  # noqa: E402
from app.providers.documents.ocr import RapidOcrEngine  # noqa: E402

SUCCESS_TARGET = 0.90


def norm(value: str) -> str:
    return "".join(value.split()).lower()


def check_page(pages, spec: dict) -> tuple[bool, str | None]:
    number = spec["page"]
    page = next((item for item in pages if item.page_number == number), None)
    if page is None:
        return False, f"page {number} missing"
    haystack = norm(page.text)
    matched = [token for token in spec["contains"] if norm(token) in haystack]
    required = spec.get("min_matches", len(spec["contains"]))
    if len(matched) < required:
        return False, f"page {number}: matched {len(matched)}/{required} tokens {spec['contains']}"
    return True, None


def check_attachments(attachments, specs: list[dict]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for spec in specs:
        found = next((item for item in attachments if item.filename == spec["filename"]), None)
        if found is None:
            failures.append(f"attachment {spec['filename']} missing")
            continue
        if "parsed" in spec and found.parsed is not spec["parsed"]:
            failures.append(f"attachment {spec['filename']}: parsed={found.parsed} expected {spec['parsed']}")
        if "skip_reason" in spec and found.skip_reason != spec["skip_reason"]:
            failures.append(f"attachment {spec['filename']}: skip_reason={found.skip_reason} expected {spec['skip_reason']}")
    return not failures, failures


def run_sample(sample: dict, engine) -> dict:
    path = CORPUS_DIR / sample["file"]
    data = path.read_bytes()
    expect = sample["expect"]
    started = time.perf_counter()
    record = {"id": sample["id"], "file": sample["file"], "format": sample["format"], "expected": expect}
    try:
        doc = parse_document(sample["file"], data, ocr=engine)
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        record["outcome"] = "success"
        record["pages"] = len(doc.pages)
        record["sources"] = [page.source for page in doc.pages]
        record["used_ocr"] = doc.used_ocr
        record["ocr_pages"] = sum(1 for page in doc.pages if page.source == "ocr")
        record["warnings"] = list(doc.warnings)
        record["attachments"] = [
            {"filename": item.filename, "size_bytes": item.size_bytes, "parsed": item.parsed, "skip_reason": item.skip_reason}
            for item in doc.attachments
        ]
        failures: list[str] = []
        if expect["outcome"] != "success":
            failures.append(f"expected error {expect['code']} but parsed successfully")
        if doc.format != sample["format"]:
            failures.append(f"format={doc.format} expected {sample['format']}")
        if len(doc.pages) < expect.get("min_pages", 1):
            failures.append(f"pages={len(doc.pages)} expected >= {expect.get('min_pages', 1)}")
        record["page_checks"] = []
        for spec in expect.get("checks", []):
            passed, failure = check_page(doc.pages, spec)
            record["page_checks"].append({"page": spec["page"], "passed": passed})
            if failure:
                failures.append(failure)
        if "attachments" in expect:
            passed, attachment_failures = check_attachments(doc.attachments, expect["attachments"])
            record["attachment_check_passed"] = passed
            failures.extend(attachment_failures)
        record["failures"] = failures
        record["passed"] = not failures
    except ParseError as exc:
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        record["outcome"] = "error"
        record["error_code"] = exc.code.value
        record["error_details"] = exc.details
        record["passed"] = expect["outcome"] == "error" and exc.code.value == expect["code"]
        record["failures"] = [] if record["passed"] else [f"expected {expect.get('code')} got {exc.code.value}"]
    except Exception as exc:  # harness must classify crashes separately
        record["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        record["outcome"] = "crash"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["passed"] = False
        record["failures"] = [record["error"]]
    return record


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def versions() -> dict:
    pins = {"pdfplumber": "pdfplumber", "pypdf": "pypdf", "Pillow": "pillow", "rapidocr": "rapidocr", "onnxruntime": "onnxruntime"}
    found = {}
    for label, package in pins.items():
        try:
            found[label] = metadata.version(package)
        except metadata.PackageNotFoundError:
            found[label] = "not-installed"
    return found


def build_report(results: dict, ran_at: datetime) -> str:
    samples = results["samples"]
    metrics = results["metrics"]
    lines: list[str] = []
    counter = {"n": 0}

    def heading(title: str) -> None:
        counter["n"] += 1
        lines.append("")
        lines.append(f"## {counter['n']}. {title}")
        lines.append("")

    verdict = "PASS" if metrics["passed"] else "FAIL"
    lines.append("# Exporbit POC-03 验证报告：PDF/图片/EML 解析")
    lines.append("")
    lines.append(f"- 验证时间（UTC）：{ran_at.isoformat()}")
    lines.append(f"- 语料：backend/data/poc03_corpus/manifest.json（{len(samples)} 个合成样本；不含真实客户数据）")
    lines.append(f"- 解析栈：pdfplumber {metrics['versions']['pdfplumber']} / pypdf {metrics['versions']['pypdf']} / Pillow {metrics['versions']['Pillow']} / RapidOCR {metrics['versions']['rapidocr']}（onnxruntime {metrics['versions']['onnxruntime']}）")
    lines.append("- 附件策略：不执行任何附件内容；可执行文件与未知类型仅登记后跳过")
    lines.append(f"- 结论：**{verdict}**")

    heading("成功标准")
    lines.append("| 标准 | 目标 | 实测 | 通过 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 有效样本解析成功率 | ≥ {pct(SUCCESS_TARGET)} | {pct(metrics['success_rate'])}（{metrics['success_passed']}/{metrics['success_total']}） | {'✅' if metrics['success_rate'] >= SUCCESS_TARGET else '❌'} |")
    lines.append(f"| 页级定位/溯源校验 | 100% | {pct(metrics['page_check_rate']) if metrics['page_checks_total'] else 'N/A'}（{metrics['page_checks_passed']}/{metrics['page_checks_total']}） | {'✅' if metrics['page_checks_passed'] == metrics['page_checks_total'] else '❌'} |")
    lines.append(f"| 受控失败错误码精确率 | 100% | {pct(metrics['controlled_rate'])}（{metrics['controlled_passed']}/{metrics['controlled_total']}） | {'✅' if metrics['controlled_passed'] == metrics['controlled_total'] else '❌'} |")
    lines.append(f"| 附件策略校验 | 100% | {pct(metrics['attachment_rate']) if metrics['attachment_checks_total'] else 'N/A'}（{metrics['attachment_passed']}/{metrics['attachment_checks_total']}） | {'✅' if metrics['attachment_passed'] == metrics['attachment_checks_total'] else '❌'} |")

    heading("逐样本结果")
    lines.append("| 样本 | 格式 | 结果 | 页数 | OCR 页 | 耗时 ms | 页面校验 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for item in samples:
        page_checks = item.get("page_checks", [])
        page_text = f"{sum(1 for check in page_checks if check['passed'])}/{len(page_checks)}" if page_checks else "—"
        outcome = item["outcome"] if item["outcome"] == "success" else f"error:{item.get('error_code', 'crash')}"
        pages = item.get("pages", "—")
        ocr_pages = item.get("ocr_pages", "—")
        lines.append(f"| {item['id']} | {item['format']} | {outcome} | {pages} | {ocr_pages} | {item['elapsed_ms']} | {page_text} | {'✅' if item['passed'] else '❌'} |")
    failures = [(item["id"], failure) for item in samples for failure in item.get("failures", [])]
    if failures:
        lines.append("")
        lines.append("失败明细：")
        for sample_id, failure in failures:
            lines.append(f"- {sample_id}: {failure}")

    heading("页级溯源样本")
    lines.append("`source` 取值：`text_layer`（PDF 文本层）、`ocr`（渲染后 OCR）、`email_body`（邮件正文）、`attachment:<filename>`（附件内页）。")
    lines.append("")
    lines.append("| 样本 | 页级来源 |")
    lines.append("|---|---|")
    for item in samples:
        if item["outcome"] == "success" and item.get("sources"):
            lines.append(f"| {item['id']} | {', '.join(item['sources'])} |")

    heading("受控失败")
    lines.append("| 样本 | 期望错误码 | 实际错误码 | 细节 |")
    lines.append("|---|---|---|---|")
    for item in samples:
        if item["outcome"] != "success":
            details = json.dumps(item.get("error_details") or item.get("error") or {}, ensure_ascii=False)
            lines.append(f"| {item['id']} | {item['expected'].get('code')} | {item.get('error_code', item.get('error', 'crash'))} | {details} |")

    heading("附件策略")
    lines.append("| 样本 | 附件 | 大小 B | 已解析 | 跳过原因 |")
    lines.append("|---|---|---|---|---|")
    for item in samples:
        for attachment in item.get("attachments", []):
            lines.append(f"| {item['id']} | {attachment['filename']} | {attachment['size_bytes']} | {attachment['parsed']} | {attachment['skip_reason'] or '—'} |")

    heading("性能")
    latencies = [item["elapsed_ms"] for item in samples]
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 样本耗时 中位数 / 均值 / 最大 | {int(statistics.median(latencies))} / {int(statistics.mean(latencies))} / {max(latencies)} ms |")
    lines.append(f"| OCR 渲染页数合计 | {metrics['ocr_pages_total']} |")
    lines.append(f"| 解析告警 | {metrics['warnings_total']} 条 |")

    heading("边界与限制")
    lines.append("- OCR 依赖 RapidOCR（PP-OCRv6，Apache-2.0）+ onnxruntime，本地推理；首次加载模型约 2.5 秒，单页 2 秒级，不适合同步请求路径，接入时应走后台任务。")
    lines.append("- 旋转检测仅在 OCR 置信度低或文本过短时尝试 90/180/270；真实照片的透视、模糊、复杂版式未覆盖，OCR 语句级准确率不参与本次评分。")
    lines.append("- 页级定位为页号 + 文本块拼接级别，未保留字符级坐标；如需高亮引用，后续需保存 bbox。")
    lines.append("- EML 只读取正文与受支持附件（PDF/图片），不执行内容、不解析压缩包、不递归嵌套邮件；HTML 正文仅做标签剥离。")
    lines.append("- 附件上限 10 MB、文件上限 25 MB、PDF 上限 50 页为当前默认值，需按业务确认（docs/DEVELOPMENT_ROADMAP.md 未决策项）。")
    lines.append("- 语料为合成数据；未包含加密 Office、宏文档、多语言混排、双栏排版等真实分布样本。")
    lines.append("- 未接入 /inquiries 业务路径；解析结果持久化与原文快照属下一步（阶段 1 Inquiry Foundation）。")
    return "\n".join(lines) + "\n"


def main() -> None:
    manifest = json.loads((CORPUS_DIR / "manifest.json").read_text(encoding="utf-8"))
    engine = RapidOcrEngine()
    ran_at = datetime.now(timezone.utc)
    samples = [run_sample(sample, engine) for sample in manifest["samples"]]

    success_samples = [item for item in samples if item["expected"]["outcome"] == "success"]
    success_passed = sum(1 for item in success_samples if item["passed"])
    success_rate = success_passed / len(success_samples)
    controlled = [item for item in samples if item["expected"]["outcome"] == "error"]
    controlled_passed = sum(1 for item in controlled if item["passed"])
    page_checks_total = sum(len(item.get("page_checks", [])) for item in samples)
    page_checks_passed = sum(1 for item in samples for check in item.get("page_checks", []) if check["passed"])
    attachment_checks_total = sum(1 for item in samples if "attachment_check_passed" in item)
    attachment_passed = sum(1 for item in samples if item.get("attachment_check_passed"))
    metrics = {
        "success_total": len(success_samples),
        "success_passed": success_passed,
        "success_rate": round(success_rate, 4),
        "controlled_total": len(controlled),
        "controlled_passed": controlled_passed,
        "controlled_rate": round(controlled_passed / len(controlled), 4),
        "page_checks_total": page_checks_total,
        "page_checks_passed": page_checks_passed,
        "page_check_rate": round(page_checks_passed / page_checks_total, 4) if page_checks_total else 0.0,
        "attachment_checks_total": attachment_checks_total,
        "attachment_passed": attachment_passed,
        "attachment_rate": round(attachment_passed / attachment_checks_total, 4) if attachment_checks_total else 0.0,
        "ocr_pages_total": sum(item.get("ocr_pages", 0) for item in samples),
        "warnings_total": sum(len(item.get("warnings", [])) for item in samples),
        "versions": versions(),
    }
    metrics["passed"] = (
        success_rate >= SUCCESS_TARGET
        and controlled_passed == len(controlled)
        and page_checks_passed == page_checks_total
        and attachment_passed == attachment_checks_total
    )
    results = {
        "meta": {
            "poc": "POC-03",
            "ran_at": ran_at.isoformat(),
            "corpus": (CORPUS_DIR / "manifest.json").relative_to(PROJECT_DIR).as_posix(),
        },
        "metrics": metrics,
        "samples": samples,
    }
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "POC_03_RESULTS.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = build_report(results, ran_at)
    (OUTPUTS_DIR / "POC_03_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")

    print(f"success {success_passed}/{len(success_samples)} ({pct(success_rate)})")
    print(f"controlled failures {controlled_passed}/{len(controlled)}")
    print(f"page checks {page_checks_passed}/{page_checks_total}")
    print(f"attachment checks {attachment_passed}/{attachment_checks_total}")
    print(f"verdict: {'PASS' if metrics['passed'] else 'FAIL'}")
    for item in samples:
        if not item["passed"]:
            print(f"FAIL {item['id']}: {item.get('failures')}")


if __name__ == "__main__":
    main()
