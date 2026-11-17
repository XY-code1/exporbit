"""Local knowledge providers for POC-05.

`FixtureLiveProvider` simulates a validated LIVE integration (it can be taken
offline to exercise failure isolation). `DemoZhihuProvider` returns fixed DEMO
content and is always marked `is_demo=True`. No network access, no real source
content: both are synthetic fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.providers.knowledge.contracts import (
    KnowledgeErrorCode,
    KnowledgeProviderError,
    ProviderHealth,
    ProviderMode,
    SourceCategory,
    SourceDocument,
)

DEFAULT_LIVE_CONTENT = (
    "合成 fixture，仅用于验证证据快照与溯源，不代表真实法规。PROV-TOKEN-EU-01\n"
    "无线设备进入欧盟市场通常需要 CE 标识与符合性声明。\n"
    "带电池产品需提供电池指令相关文件与回收标识。\n"
    "进口商应保留技术文件与供应链尽职调查记录。\n"
    "产品标签需包含制造商/进口商信息与可追溯批次。"
)

DEMO_ZHIHU_CONTENT = (
    "DEMO-TOKEN-ZH-01 固定演示数据，不是实时知乎搜索。\n"
    "社区讨论摘要（演示）：德国客户常关注 CE 认证、包装回收标识和交期；"
    "部分买家会要求德语说明书。以上为社区经验，不代表法规。"
)


@dataclass
class FixtureLiveProvider:
    code: str = "fixture_live"
    category: SourceCategory = SourceCategory.OVERSEAS
    mode: ProviderMode = ProviderMode.LIVE
    title: str = "海外公开资料：欧盟无线耳机进口合规要点（合成 fixture）"
    canonical_url: str | None = "https://example.com/synthetic/eu-wireless-earbuds"
    publisher: str = "Example Trade Authority (synthetic)"
    content: str = DEFAULT_LIVE_CONTENT
    published_at: datetime = field(default_factory=lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    available: bool = True

    def go_offline(self) -> None:
        self.available = False

    def go_online(self) -> None:
        self.available = True

    async def fetch(self, query: str) -> SourceDocument:
        if not self.available:
            raise KnowledgeProviderError(KnowledgeErrorCode.UNAVAILABLE, "fixture provider is offline")
        return SourceDocument(
            title=self.title,
            canonical_url=self.canonical_url,
            content=self.content,
            source_category=self.category,
            provider_mode=self.mode,
            is_demo=False,
            publisher=self.publisher,
            published_at=self.published_at,
            usage_note="Synthetic fixture content; not a real external source.",
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth("AVAILABLE" if self.available else "UNAVAILABLE")


@dataclass
class DemoZhihuProvider:
    code: str = "zhihu_demo"
    category: SourceCategory = SourceCategory.ZHIHU
    mode: ProviderMode = ProviderMode.DEMO
    title: str = "知乎演示：蓝牙耳机出口德国的常见问题（DEMO）"
    canonical_url: str | None = "https://demo.exporbit.local/zhihu/wireless-earbuds-germany"
    content: str = DEMO_ZHIHU_CONTENT

    async def fetch(self, query: str) -> SourceDocument:
        return SourceDocument(
            title=self.title,
            canonical_url=self.canonical_url,
            content=self.content,
            source_category=self.category,
            provider_mode=self.mode,
            is_demo=True,
            publisher="Zhihu（DEMO 数据）",
            published_at=None,
            usage_note="Fixed demo content; not a live Zhihu integration.",
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth("AVAILABLE", "demo data")


PROVIDER_SEEDS: tuple[dict, ...] = (
    {
        "code": "fixture_live",
        "category": "OVERSEAS",
        "display_name": "海外公开资料（LIVE-like fixture）",
        "mode": "LIVE",
        "enabled": True,
    },
    {
        "code": "zhihu_demo",
        "category": "ZHIHU",
        "display_name": "知乎演示数据（DEMO）",
        "mode": "DEMO",
        "enabled": True,
    },
    {
        "code": "manual_import",
        "category": None,
        "display_name": "手工导入证据",
        "mode": "MANUAL",
        "enabled": True,
    },
    {
        "code": "zhihu_live",
        "category": "ZHIHU",
        "display_name": "知乎实时来源（PLANNED，未启用）",
        "mode": "PLANNED",
        "enabled": False,
    },
)
