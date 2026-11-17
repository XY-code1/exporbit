"""Local, license-safe knowledge providers used by POC-05 (no network)."""
from app.providers.knowledge.contracts import (
    KnowledgeErrorCode,
    KnowledgeProvider,
    KnowledgeProviderError,
    ProviderHealth,
    ProviderMode,
    SourceCategory,
    SourceDocument,
)
from app.providers.knowledge.fixtures import (
    DEFAULT_LIVE_CONTENT,
    DEMO_ZHIHU_CONTENT,
    PROVIDER_SEEDS,
    DemoZhihuProvider,
    FixtureLiveProvider,
)

__all__ = [
    "DEFAULT_LIVE_CONTENT",
    "DEMO_ZHIHU_CONTENT",
    "PROVIDER_SEEDS",
    "DemoZhihuProvider",
    "FixtureLiveProvider",
    "KnowledgeErrorCode",
    "KnowledgeProvider",
    "KnowledgeProviderError",
    "ProviderHealth",
    "ProviderMode",
    "SourceCategory",
    "SourceDocument",
]
