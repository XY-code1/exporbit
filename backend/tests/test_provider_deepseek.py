"""DeepSeek adapter tests using an httpx mock transport (no real network)."""
import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from app.providers.contracts import Message, MessageRole, ProviderError, ProviderErrorCode
from app.providers.deepseek import DeepSeekProvider


class Sample(BaseModel):
    value: str


class SampleWithField(Sample):
    count: int


def _response(content: str | None, status: int = 200, usage: dict | None = None, finish_reason: str = "stop") -> httpx.Response:
    body = {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))


async def _noop(_: float) -> None:
    return None


def _provider(handler, *, max_retries: int = 2, api_key: str = "test-key"):
    return DeepSeekProvider(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        transport=httpx.MockTransport(handler),
        max_retries=max_retries,
        sleep=_noop,
    )


def _messages() -> list[Message]:
    return [Message(role=MessageRole.SYSTEM, content="json prompt"), Message(role=MessageRole.USER, content="extract this")]


def _run(coro):
    return asyncio.run(coro)


def test_success_valid_json():
    calls = []

    def handler(request):
        calls.append(request)
        return _response(json.dumps({"value": "ok", "count": 3}))

    provider = _provider(handler)
    result = _run(
        provider.generate_structured(
            purpose="p", messages=_messages(), output_schema=SampleWithField, temperature=0.0, max_tokens=100
        )
    )
    assert result.data == SampleWithField(value="ok", count=3)
    assert result.provider == "deepseek"
    assert result.usage.prompt_tokens == 10
    assert result.usage.total_tokens == 15
    assert result.latency_ms >= 0
    assert result.finish_reason == "stop"
    assert result.repair_used is False
    assert result.attempts == 1
    assert len(calls) == 1
    sent = json.loads(calls[0].content)
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["model"] == "deepseek-chat"


def test_blank_content_is_retried_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return _response("   ")
        return _response(json.dumps({"value": "ok", "count": 1}))

    result = _run(_provider(handler).generate_structured(purpose="p", messages=_messages(), output_schema=SampleWithField))
    assert result.data.value == "ok"
    assert result.attempts == 2
    assert len(calls) == 2


def test_invalid_json_retries_then_classifies():
    calls = []

    def handler(request):
        calls.append(request)
        return _response("this is not json at all")

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.INVALID_OUTPUT
    assert error.details["attempts"] == 3
    assert len(calls) == 3


def test_schema_mismatch_triggers_single_repair_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return _response(json.dumps({"wrong": "shape"}))
        return _response(json.dumps({"value": "ok"}))

    result = _run(_provider(handler).generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    assert result.data == Sample(value="ok")
    assert result.repair_used is True
    assert result.attempts == 2
    assert len(calls) == 2
    repair_payload = json.loads(calls[1].content)
    assert len(repair_payload["messages"]) == 4  # system, user, assistant(invalid), user(repair)
    assert repair_payload["messages"][2]["role"] == "assistant"
    assert "schema" in repair_payload["messages"][3]["content"]


def test_schema_mismatch_repair_fails_classifies_invalid_output():
    calls = []

    def handler(request):
        calls.append(request)
        return _response(json.dumps({"wrong": "shape"}))

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.INVALID_OUTPUT
    assert "validation_errors" in error.details
    assert len(calls) == 2  # original + one repair, no further retries


def test_rate_limit_retries_then_classifies():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            429, json={"error": "rate limited"}, headers={"Retry-After": "0"}, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        )

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.RATE_LIMIT
    assert error.retryable is True
    assert error.details["attempts"] == 3
    assert len(calls) == 3


def test_server_error_retries_then_classifies_unavailable():
    calls = []

    def handler(request):
        calls.append(request)
        return _response('{"error": "boom"}', status=503)

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.UNAVAILABLE
    assert error.details["attempts"] == 3
    assert len(calls) == 3


def test_timeout_retries_then_classifies():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("timed out")

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.TIMEOUT
    assert error.details["attempts"] == 3
    assert len(calls) == 3


def test_configuration_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return _response('{"error": "unauthorized"}', status=401)

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.CONFIGURATION
    assert error.retryable is False
    assert error.details["http_status"] == 401
    assert error.details["attempts"] == 1
    assert len(calls) == 1


def test_missing_api_key_fails_before_network():
    calls = []

    def handler(request):
        calls.append(request)
        return _response(json.dumps({"value": "ok"}))

    provider = _provider(handler, api_key="")
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.CONFIGURATION
    assert len(calls) == 0


def test_malformed_body_classifies_invalid_output():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text="not json", request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))

    provider = _provider(handler)
    with pytest.raises(ProviderError) as exc_info:
        _run(provider.generate_structured(purpose="p", messages=_messages(), output_schema=Sample))
    error = exc_info.value
    assert error.code is ProviderErrorCode.INVALID_OUTPUT
    assert len(calls) == 3
