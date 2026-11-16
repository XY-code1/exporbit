"""LLM provider contracts: message/result types and stable error codes.

Business code depends on these interfaces only. Provider adapters implement
`LLMProvider` and raise `ProviderError` with a stable `ProviderErrorCode` so
failures can be classified, logged, and surfaced without leaking vendor details.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    role: MessageRole
    content: str

    def as_openai_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}


class ProviderErrorCode(str, Enum):
    TIMEOUT = "PROVIDER_TIMEOUT"
    RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    INVALID_OUTPUT = "PROVIDER_INVALID_OUTPUT"
    CONFIGURATION = "PROVIDER_CONFIGURATION"
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"


class ProviderError(Exception):
    """Stable, classifiable provider failure.

    `details` may carry diagnostics such as http_status, attempts, or a bounded
    excerpt of validation errors. It must never contain credentials.
    """

    def __init__(
        self,
        code: ProviderErrorCode,
        message: str,
        *,
        retryable: bool = False,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = details or {}


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResult:
    """A provider response whose payload passed Pydantic validation.

    Unvalidated text is never exposed as a business object.
    """

    data: BaseModel
    provider: str
    model: str
    usage: LLMUsage
    latency_ms: int
    finish_reason: str | None
    raw_content: str
    repair_used: bool = False
    attempts: int = 1


@runtime_checkable
class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        purpose: str,
        messages: list[Message],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> LLMResult: ...
