"""Knowledge provider contracts for evidence provenance (POC-05).

The POC uses local fixtures and fixed DEMO data; network adapters (Zhihu,
overseas sources) implement the same protocol later. Business code depends on
these types only, never on a vendor SDK or page structure (docs/PROVIDER_DESIGN.md).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable


class SourceCategory(str, Enum):
    CUSTOMER_INQUIRY = "CUSTOMER_INQUIRY"
    ENTERPRISE = "ENTERPRISE"
    ZHIHU = "ZHIHU"
    OFFICIAL = "OFFICIAL"
    OVERSEAS = "OVERSEAS"


class ProviderMode(str, Enum):
    LIVE = "LIVE"
    MANUAL = "MANUAL"
    DEMO = "DEMO"
    PLANNED = "PLANNED"


class KnowledgeErrorCode(str, Enum):
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    NOT_FOUND = "PROVIDER_NOT_FOUND"


class KnowledgeProviderError(Exception):
    """Stable provider failure; must never carry credentials or page-only details."""

    def __init__(self, code: KnowledgeErrorCode, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class SourceDocument:
    """Normalized provider document; `is_demo` must match `provider_mode`."""

    title: str
    canonical_url: str | None
    content: str
    source_category: SourceCategory
    provider_mode: ProviderMode
    is_demo: bool
    publisher: str | None = None
    published_at: datetime | None = None
    usage_note: str | None = None


@dataclass(frozen=True)
class ProviderHealth:
    status: str  # AVAILABLE | UNAVAILABLE
    detail: str | None = None


@runtime_checkable
class KnowledgeProvider(Protocol):
    code: str
    category: SourceCategory
    mode: ProviderMode

    async def fetch(self, query: str) -> SourceDocument: ...

    async def health(self) -> ProviderHealth: ...
