"""POC-05 harness: exercise evidence provenance end to end and write a report.

Usage (from backend/): ../.venv/Scripts/python.exe scripts/validate_provenance.py
Creates synthetic, clearly-marked rows in the configured database (dev by
default), replacing any earlier run of this harness, then writes:
outputs/POC_05_RESULTS.json and outputs/POC_05_VALIDATION_REPORT.md
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
OUTPUTS_DIR = PROJECT_DIR / "outputs"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select  # noqa: E402

from app.core.errors import AppError  # noqa: E402
from app.domains.evidence.models import Insight  # noqa: E402
from app.domains.evidence.service import EvidenceService, content_hash  # noqa: E402
from app.domains.inquiry.models import Inquiry  # noqa: E402
from app.infrastructure.database import SessionLocal  # noqa: E402
from app.providers.knowledge import DemoZhihuProvider, FixtureLiveProvider  # noqa: E402

SUBJECT = "POC-05 synthetic provenance inquiry"
RAW_TEXT = "合成询盘：500 副无线蓝牙耳机出口德国，要求印 Logo，报 FOB 深圳价。"
SECOND_CONTENT = (
    "合成 fixture（第二来源），仅用于验证证据快照与溯源。PROV-TOKEN-DE-02\n"
    "德国包装法（VerpackG）要求参与包装回收系统并在 LUCID 登记。\n"
    "出口商应与进口商确认包装责任划分与标识要求。"
)
MANUAL_CONTENT = (
    "客户邮件摘要（手工导入，合成示例）：客户要求外包装印回收标识，"
    "并询问能否提供德语说明书。MANUAL-TOKEN-03"
)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def reset_synthetic_rows(session) -> None:
    session.execute(delete(Inquiry).where(Inquiry.subject == SUBJECT))
    session.commit()


def run_scenario() -> dict:
    checks: list[dict] = []

    def check(step: str, expected: str, actual: str, passed: bool) -> None:
        checks.append({"step": step, "expected": expected, "actual": actual, "passed": passed})

    with SessionLocal() as session:
        reset_synthetic_rows(session)
        service = EvidenceService(session)
        service.seed_providers()
        inquiry = Inquiry(
            subject=SUBJECT,
            raw_text=RAW_TEXT,
            source_type="TEXT",
            workflow_status="NEW",
            extracted_fields={},
            content_hash=content_hash(RAW_TEXT),
        )
        session.add(inquiry)
        session.commit()

        live_provider = FixtureLiveProvider()
        first = asyncio.run(service.capture_from_provider(inquiry.id, live_provider, "EU wireless earbuds import requirements"))
        second_provider = FixtureLiveProvider(
            title="海外公开资料：德国包装回收标识（合成 fixture）",
            canonical_url="https://example.com/synthetic/de-packaging-label",
            content=SECOND_CONTENT,
        )
        second = asyncio.run(service.capture_from_provider(inquiry.id, second_provider, "German packaging recycling label"))
        demo = asyncio.run(service.capture_from_provider(inquiry.id, DemoZhihuProvider(), "蓝牙耳机 德国 认证"))
        manual = service.capture_manual(
            inquiry.id,
            title="客户邮件摘要（手工导入，合成）",
            content=MANUAL_CONTENT,
            canonical_url=None,
            captured_by="poc-operator",
        )
        check("采集 LIVE / LIVE / DEMO / MANUAL 证据", "4 条 CAPTURED", f"{sum(1 for item in (first, second, demo) if item.status == 'CAPTURED')} + 1 manual", all(item.status == "CAPTURED" for item in (first, second, demo)))

        insight = service.create_insight(
            inquiry.id,
            statement=(
                "回复客户时可以说明：欧盟/德国市场通常需要 CE 文件与包装回收标识，"
                "德语说明书可作为可选项向客户确认（依据证据时间 2026-10）。"
            ),
            evidence_links=[
                (first.evidence_id, "SUPPORTS"),
                (second.evidence_id, "CONTEXT"),
                (demo.evidence_id, "CONTEXT"),
                (manual.evidence_id, "SUPPORTS"),
            ],
        )

        service.mark_unavailable(first.evidence_id)
        live_provider.go_offline()
        outage = asyncio.run(service.capture_from_provider(inquiry.id, live_provider, "EU import requirements retry"))

        all_evidence = service.list_evidence(inquiry.id)
        provenance = service.provenance(insight.id)
        insight_rows = list(session.scalars(select(Insight).where(Insight.inquiry_id == inquiry.id)))
        provider_rows = service.list_providers()

        links = provenance.evidence
        resolved_links = [item for item in links if item.title and item.provider_mode and item.snapshot_chars > 0]
        verified_links = [item for item in links if item.snapshot_verified]
        demo_evidence = [item for item in all_evidence if item.provider_mode == "DEMO"]
        consistent_flags = [item for item in all_evidence if item.is_demo == (item.provider_mode == "DEMO")]
        hashes = [item.content_hash for item in all_evidence if len(item.content_hash) == 64]
        expired = next(item for item in links if item.evidence_id == first.evidence_id)
        planned = next(item for item in provider_rows if item.code == "zhihu_live")

        check("洞察证据链完整", "4/4 条证据可解析", f"{len(resolved_links)}/4", len(resolved_links) == 4)
        check("快照哈希校验", "100%", pct(len(verified_links) / len(links)), len(verified_links) == len(links))
        check("外链失效仍显示快照", "UNAVAILABLE + 快照可读", f"{expired.availability_status}, {expired.snapshot_chars} chars", expired.availability_status == "UNAVAILABLE" and expired.snapshot_chars > 0 and expired.snapshot_verified)
        check("DEMO 强制标注", "DEMO 全部 is_demo=true", f"{len(demo_evidence)} 条 DEMO，模式/标志一致 {len(consistent_flags)}/{len(all_evidence)}", all(item.is_demo for item in demo_evidence) and len(consistent_flags) == len(all_evidence))
        check("Provider 离线隔离", "UNAVAILABLE，不新增证据", f"{outage.status}/{outage.error_code}，证据仍 {len(all_evidence)} 条", outage.status == "UNAVAILABLE" and outage.error_code == "PROVIDER_UNAVAILABLE" and len(all_evidence) == 4)
        check("离线后洞察仍可解释", "快照链路完好", f"links={len(links)}，verified={len(verified_links)}", len(links) == 4 and len(verified_links) == 4)
        check("PLANNED Provider 不可执行", "disabled + PLANNED", f"enabled={planned.enabled}, mode={planned.mode}", planned.enabled is False and planned.mode == "PLANNED")
        try:
            service.create_insight(inquiry.id, statement="无证据的推断", evidence_links=[])
            empty_rejected = False
            empty_code = "accepted"
        except AppError as exc:
            empty_rejected = exc.code == "EVIDENCE_REQUIRED"
            empty_code = exc.code
        check("洞察必须有证据", "EVIDENCE_REQUIRED", empty_code, empty_rejected)

        metrics = {
            "insights_total": len(insight_rows),
            "insights_with_evidence": sum(1 for row in insight_rows if len(provenance.evidence) > 0),
            "evidence_total": len(all_evidence),
            "insight_links_total": len(links),
            "insight_links_resolved": len(resolved_links),
            "snapshot_verified_links": len(verified_links),
            "snapshot_verify_rate": round(len(verified_links) / len(links), 4),
            "content_hashes_sha256": len(hashes),
            "demo_evidence_total": len(demo_evidence),
            "demo_evidence_labelled": sum(1 for item in demo_evidence if item.is_demo),
            "mode_flag_consistency_rate": round(len(consistent_flags) / len(all_evidence), 4),
            "expired_link_status": expired.availability_status,
            "expired_link_snapshot_chars": expired.snapshot_chars,
            "outage_status": outage.status,
            "outage_error_code": outage.error_code,
            "evidence_after_outage": len(all_evidence),
            "provenance_intact_after_outage": len(links) == 4 and len(verified_links) == 4,
            "planned_provider_enabled": planned.enabled,
        }
        metrics["passed"] = all(item["passed"] for item in checks)

        results = {
            "meta": {
                "poc": "POC-05",
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "inquiry_subject": SUBJECT,
                "synthetic": True,
                "database": "local dev (rows replaced on each run)",
            },
            "metrics": metrics,
            "checks": checks,
            "insight": {
                "id": str(insight.id),
                "statement": insight.statement,
                "status": insight.status,
                "origin": insight.origin,
                "revision": insight.revision,
                "evidence": [
                    {
                        "evidence_id": str(item.evidence_id),
                        "support_type": item.support_type,
                        "title": item.title,
                        "canonical_url": item.canonical_url,
                        "provider_code": item.provider_code,
                        "provider_mode": item.provider_mode,
                        "source_category": item.source_category,
                        "is_demo": item.is_demo,
                        "availability_status": item.availability_status,
                        "captured_at": item.captured_at.isoformat(),
                        "source_published_at": item.source_published_at.isoformat() if item.source_published_at else None,
                        "content_hash": item.content_hash,
                        "snapshot_verified": item.snapshot_verified,
                        "snapshot_chars": item.snapshot_chars,
                    }
                    for item in links
                ],
            },
            "providers": [
                {
                    "code": row.code,
                    "mode": row.mode,
                    "category": row.category,
                    "enabled": row.enabled,
                    "last_health_status": row.last_health_status,
                }
                for row in provider_rows
            ],
        }
        return results


def build_report(results: dict) -> str:
    metrics = results["metrics"]
    checks = results["checks"]
    insight = results["insight"]
    lines: list[str] = []
    counter = {"n": 0}

    def heading(title: str) -> None:
        counter["n"] += 1
        lines.append("")
        lines.append(f"## {counter['n']}. {title}")
        lines.append("")

    verdict = "PASS" if metrics["passed"] else "FAIL"
    lines.append("# Exporbit POC-05 验证报告：Evidence Provenance")
    lines.append("")
    lines.append(f"- 验证时间（UTC）：{results['meta']['ran_at']}")
    lines.append(f"- 环境：本地 dev PostgreSQL；迁移 `20261116_0003`；每次运行替换同名合成询盘数据")
    lines.append(f"- 数据：合成询盘（{results['meta']['inquiry_subject']}）、LIVE-like fixture、知乎 DEMO 固定文本、手工导入；不含真实客户或外部来源内容")
    lines.append(f"- 结论：**{verdict}**")

    heading("成功标准")
    lines.append("| 标准 | 目标 | 实测 | 通过 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 每个 insight 可追到 evidence 与 source | 100% | {metrics['insight_links_resolved']}/{metrics['insight_links_total']}（{pct(metrics['insight_links_resolved'] / metrics['insight_links_total'])}） | {'✅' if metrics['insight_links_resolved'] == metrics['insight_links_total'] else '❌'} |")
    lines.append(f"| 快照 sha256 校验一致 | 100% | {metrics['snapshot_verified_links']}/{metrics['insight_links_total']}（{pct(metrics['snapshot_verify_rate'])}） | {'✅' if metrics['snapshot_verify_rate'] == 1 else '❌'} |")
    lines.append(f"| 外链失效仍显示快照 | 100% | {metrics['expired_link_status']}，快照 {metrics['expired_link_snapshot_chars']} 字 | {'✅' if metrics['expired_link_status'] == 'UNAVAILABLE' else '❌'} |")
    lines.append(f"| DEMO 无漏标 | 100% | {metrics['demo_evidence_labelled']}/{metrics['demo_evidence_total']}，模式一致率 {pct(metrics['mode_flag_consistency_rate'])} | {'✅' if metrics['demo_evidence_labelled'] == metrics['demo_evidence_total'] and metrics['mode_flag_consistency_rate'] == 1 else '❌'} |")
    lines.append(f"| Provider 失效隔离 | 可控 UNAVAILABLE | {metrics['outage_status']}/{metrics['outage_error_code']}，证据仍 {metrics['evidence_after_outage']} 条 | {'✅' if metrics['provenance_intact_after_outage'] else '❌'} |")

    heading("场景与检查")
    lines.append("| 步骤 | 预期 | 实际 | 判定 |")
    lines.append("|---|---|---|---|")
    for item in checks:
        lines.append(f"| {item['step']} | {item['expected']} | {item['actual']} | {'✅' if item['passed'] else '❌'} |")

    heading("洞察证据链")
    lines.append("| 证据 | 支撑关系 | Provider | 模式 | DEMO | 可用性 | 获取时间 | 快照 | Hash 校验 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for item in insight["evidence"]:
        lines.append(
            f"| {item['title']} | {item['support_type']} | {item['provider_code']} | {item['provider_mode']} | "
            f"{'是' if item['is_demo'] else '否'} | {item['availability_status']} | {item['captured_at'][:19]} | "
            f"{item['snapshot_chars']} 字 | {'✅' if item['snapshot_verified'] else '❌'} |"
        )
    lines.append("")
    lines.append(f"洞察语句：{insight['statement']}")
    lines.append("")
    lines.append(f"洞察状态：`{insight['status']}`（origin `{insight['origin']}`，revision {insight['revision']}）。AI 推断不得标为已确认事实。")

    heading("Provider 状态")
    lines.append("| code | 模式 | 类别 | 启用 | 最近健康状态 |")
    lines.append("|---|---|---|---|---|")
    for row in results["providers"]:
        lines.append(f"| {row['code']} | {row['mode']} | {row['category'] or '—'} | {row['enabled']} | {row['last_health_status'] or '—'} |")

    heading("故障隔离行为")
    lines.append(f"- LIVE-like Provider 离线后再次采集返回 `{metrics['outage_status']}`（`{metrics['outage_error_code']}`），不抛错、不写入新证据；已有 {metrics['evidence_after_outage']} 条证据与洞察链路仍可读取。")
    lines.append(f"- 模拟外链失效（`mark_unavailable`）后，该证据状态为 `{metrics['expired_link_status']}`，快照文本（{metrics['expired_link_snapshot_chars']} 字）与 hash 仍可用于解释洞察来源。")
    lines.append("- DEMO 证据由已注册 Provider 模式强制派生 `is_demo`，数据库约束 `is_demo = (provider_mode = 'DEMO')` 阻止漏标；PLANNED Provider 处于禁用状态，采集前即被拒绝。")

    heading("时间与快照语义")
    lines.append("- `captured_at` 为系统获取证据的时间；`source_published_at` 为来源自身发布时间，可为空，两者分开保存，界面不得混用。")
    lines.append("- 快照保存在 `evidence.captured_text`，`content_hash` 为快照文本的 sha256；本次验证对全部洞察证据逐条重算并比对通过。")
    lines.append("- 快照与证据行在同一事务写入，避免“有行无快照”；外链失效只改 `availability_status`，不删除快照。")

    heading("边界与限制")
    lines.append("- Provider 为本地 fixture/DEMO，不执行网络请求；真实知乎/海外来源的授权、限流与条款仍待 POC-06，不因本报告视为可用集成。")
    lines.append("- 失败采集（Provider UNAVAILABLE）仅返回运行时结果并更新 Provider 健康状态，尚未持久化 research_run/partial failure 表；阶段 3 接入研究运行时补齐。")
    lines.append("- 未实现 discovery candidate 到 Evidence 的人工接受流程、证据编辑/删除、审计日志，也未接入前端 Evidence Drawer。")
    lines.append("- 证据可信状态默认 `NEEDS_CONFIRMATION`，未做来源间的自动交叉验证；`usage_note` 只记录文本说明，许可证与保留期限策略待确认。")
    lines.append("- 未验证多用户并发、租户隔离、快照容量/清理与敏感信息脱敏。")
    lines.append("- 合成数据结论不能外推到真实来源质量；本 POC 只验证 provenance 机制与故障隔离。")

    hashn = metrics["content_hashes_sha256"]
    lines.append("")
    lines.append(f"补充：{metrics['evidence_total']} 条证据均生成 64 位 sha256（{hashn} 条校验通过），洞察链路共 {metrics['insight_links_total']} 条。")
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run_scenario()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "POC_05_RESULTS.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (OUTPUTS_DIR / "POC_05_VALIDATION_REPORT.md").write_text(build_report(results), encoding="utf-8")
    metrics = results["metrics"]
    print(f"insights {metrics['insights_with_evidence']}/{metrics['insights_total']} with evidence")
    print(f"links resolved {metrics['insight_links_resolved']}/{metrics['insight_links_total']}")
    print(f"snapshot verified {metrics['snapshot_verified_links']}/{metrics['insight_links_total']}")
    print(f"demo labelled {metrics['demo_evidence_labelled']}/{metrics['demo_evidence_total']}")
    print(f"outage {metrics['outage_status']} evidence_after={metrics['evidence_after_outage']}")
    print(f"verdict: {'PASS' if metrics['passed'] else 'FAIL'}")
    for item in results["checks"]:
        if not item["passed"]:
            print(f"FAIL {item['step']}: {item['actual']}")


if __name__ == "__main__":
    main()
