"""DeepSeek chat-completions adapter (OpenAI-compatible REST, JSON output mode).

Rules implemented here follow docs/PROVIDER_DESIGN.md:
- connection errors / 429 / 5xx: up to `max_retries` retries with exponential
  backoff and jitter; 429 honors Retry-After (capped).
- schema validation failure: exactly one constrained repair request.
- 4xx configuration errors are never retried.
- the API key is never included in error messages, logs, or responses.

DeepSeek JSON mode specifics (api-docs.deepseek.com/guides/json_mode):
- `response_format: {"type": "json_object"}`; prompt must mention "json" and
  show an example; when the model output cannot be recognized as JSON the API
  replaces it with spaces, so blank content is retried as a transient failure.
"""
from __future__ import annotations

import asyncio
import json
import random
import time
from typing import Any, Awaitable, Callable

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.providers.contracts import (
    LLMProvider,
    LLMResult,
    LLMUsage,
    Message,
    MessageRole,
    ProviderError,
    ProviderErrorCode,
)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_CONFIGURATION_STATUSES = frozenset({400, 401, 403, 404, 405, 422})
_MAX_BACKOFF_SECONDS = 10.0
_MAX_REPAIR_CHARS = 4000

SleepFn = Callable[[float], Awaitable[None]]


class DeepSeekProvider:
    """Thin adapter over the DeepSeek `/chat/completions` endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: SleepFn = asyncio.sleep,
    ):
        self._api_key = api_key if api_key is not None else (settings.deepseek_api_key or "")
        self._model = model or settings.deepseek_model
        base = (base_url or settings.deepseek_base_url).rstrip("/")
        self._url = f"{base}/chat/completions"
        self._timeout = timeout_seconds or settings.deepseek_timeout_seconds
        self._max_retries = max_retries if max_retries is not None else settings.deepseek_max_retries
        self._sleep = sleep
        self._client = httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(self._timeout))

    @property
    def model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        await self._client.aclose()

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
    ) -> LLMResult:
        if not self._api_key:
            raise ProviderError(
                ProviderErrorCode.CONFIGURATION,
                "DeepSeek API key is not configured",
                details={"purpose": purpose},
            )
        model = model or self._model
        started = time.perf_counter()
        attempts = 0
        payload_messages = list(messages)
        repair_used = False

        async def post() -> httpx.Response:
            nonlocal attempts
            attempts += 1
            payload: dict[str, Any] = {
                "model": model,
                "messages": [message.as_openai_dict() for message in payload_messages],
                "response_format": {"type": "json_object"},
                "stream": False,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            headers = {"Authorization": f"Bearer {self._api_key}"}
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            try:
                return await self._client.post(
                    self._url, headers=headers, json=payload, timeout=timeout_seconds or self._timeout
                )
            except httpx.TimeoutException:
                raise ProviderError(
                    ProviderErrorCode.TIMEOUT,
                    "provider request timed out",
                    retryable=True,
                    details={"purpose": purpose},
                ) from None
            except httpx.HTTPError as exc:
                raise ProviderError(
                    ProviderErrorCode.UNAVAILABLE,
                    "provider connection failed",
                    retryable=True,
                    details={"purpose": purpose, "error_type": type(exc).__name__},
                ) from None

        def parse_content(response: httpx.Response) -> tuple[str, LLMUsage, str | None]:
            if response.status_code in _CONFIGURATION_STATUSES:
                raise ProviderError(
                    ProviderErrorCode.CONFIGURATION,
                    f"provider rejected request with status {response.status_code}",
                    details={"purpose": purpose, "http_status": response.status_code},
                )
            if response.status_code in _RETRYABLE_STATUSES:
                raise ProviderError(
                    ProviderErrorCode.RATE_LIMIT if response.status_code == 429 else ProviderErrorCode.UNAVAILABLE,
                    f"provider returned status {response.status_code}",
                    retryable=True,
                    details={
                        "purpose": purpose,
                        "http_status": response.status_code,
                        "retry_after": response.headers.get("Retry-After"),
                    },
                )
            if response.status_code != 200:
                raise ProviderError(
                    ProviderErrorCode.UNAVAILABLE,
                    f"unexpected provider status {response.status_code}",
                    retryable=True,
                    details={"purpose": purpose, "http_status": response.status_code},
                )
            try:
                body = response.json()
                choice = body["choices"][0]
                content = choice["message"]["content"] or ""
                usage_body = body.get("usage") or {}
                usage = LLMUsage(
                    prompt_tokens=int(usage_body.get("prompt_tokens") or 0),
                    completion_tokens=int(usage_body.get("completion_tokens") or 0),
                    total_tokens=int(usage_body.get("total_tokens") or 0),
                )
                return content, usage, choice.get("finish_reason")
            except (ValueError, KeyError, IndexError, TypeError):
                raise ProviderError(
                    ProviderErrorCode.INVALID_OUTPUT,
                    "provider response body is malformed",
                    retryable=True,
                    details={"purpose": purpose},
                ) from None

        while True:
            try:
                response = await post()
                content, usage, finish_reason = parse_content(response)
            except ProviderError as exc:
                if not exc.retryable or attempts > self._max_retries:
                    exc.details = {**exc.details, "attempts": attempts}
                    raise
                await self._backoff(attempts, exc.details.get("retry_after"))
                continue

            if not content.strip():
                # DeepSeek JSON mode blank-out: docs recommend retrying the request.
                if attempts > self._max_retries:
                    raise ProviderError(
                        ProviderErrorCode.INVALID_OUTPUT,
                        "provider returned blank content",
                        details={"purpose": purpose, "attempts": attempts},
                    )
                await self._backoff(attempts, None)
                continue

            try:
                json.loads(content)
            except ValueError:
                if attempts > self._max_retries:
                    raise ProviderError(
                        ProviderErrorCode.INVALID_OUTPUT,
                        "provider returned invalid JSON",
                        details={"purpose": purpose, "attempts": attempts},
                    )
                await self._backoff(attempts, None)
                continue

            try:
                data = output_schema.model_validate_json(content)
            except ValidationError as exc:
                if repair_used or attempts > self._max_retries:
                    raise ProviderError(
                        ProviderErrorCode.INVALID_OUTPUT,
                        "provider output failed schema validation",
                        details={"purpose": purpose, "attempts": attempts, "validation_errors": exc.errors()[:10]},
                    ) from None
                repair_used = True
                payload_messages = self._repair_messages(payload_messages, content, exc)
                continue

            latency_ms = int((time.perf_counter() - started) * 1000)
            return LLMResult(
                data=data,
                provider="deepseek",
                model=model,
                usage=usage,
                latency_ms=latency_ms,
                finish_reason=finish_reason,
                raw_content=content,
                repair_used=repair_used,
                attempts=attempts,
            )

    @staticmethod
    def _repair_messages(
        messages: list[Message], invalid_content: str, validation_error: ValidationError
    ) -> list[Message]:
        compact = invalid_content.strip()
        if len(compact) > _MAX_REPAIR_CHARS:
            compact = compact[:_MAX_REPAIR_CHARS] + "…(截断)"
        errors = json.dumps(validation_error.errors()[:10], ensure_ascii=False)
        instruction = (
            "你上一次输出的 JSON 没有通过 schema 校验。请根据以下错误修正后重新输出，"
            f"只输出 JSON 对象本身，不要输出任何解释：\n{errors}"
        )
        return messages + [
            Message(role=MessageRole.ASSISTANT, content=compact),
            Message(role=MessageRole.USER, content=instruction),
        ]

    async def _backoff(self, attempts: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                delay = min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                delay = 0.0
        else:
            delay = min(1.0 * (2 ** (attempts - 1)) + random.uniform(0, 0.5), _MAX_BACKOFF_SECONDS)
        if delay > 0:
            await self._sleep(delay)
