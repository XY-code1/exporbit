"""Inquiry extraction application service.

Orchestrates the LLM provider for the `inquiry_extraction` purpose, records a
`model_run` for every call (purpose, model, tokens, latency, input hash, error
classification), and enforces human-edit precedence: AI proposals only fill
fields that are missing or not yet human-confirmed.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from uuid import UUID

from app.domains.extraction.prompts import PURPOSE_CONFIGS
from app.domains.extraction.schemas import InquiryExtraction
from app.domains.llm_run.models import LLMRun
from app.domains.llm_run.repository import LLMRunRepository
from app.providers.contracts import LLMProvider, Message, MessageRole, ProviderError

# Human-edited values carry CONFIRMED / INFERRED and are never overwritten by AI
# re-runs. Proposals may fill missing fields or fields awaiting confirmation.
PROTECTED_STATUSES = frozenset({"CONFIRMED", "INFERRED"})


def input_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def merge_extraction(existing: dict, extracted: InquiryExtraction) -> tuple[dict, bool]:
    """Merge AI proposals into persisted fields without overwriting human edits.

    Returns (merged_dict, changed). A field is protected when its persisted
    status is CONFIRMED or INFERRED and it has a non-null value; protected
    fields are kept as-is. Unknown persisted keys are preserved untouched.
    """
    merged: dict = {}
    changed = False
    for name, field in extracted:
        proposal = field.model_dump(mode="json")
        current = existing.get(name) if isinstance(existing, dict) else None
        current_status = current.get("status") if isinstance(current, dict) else None
        current_value = current.get("value") if isinstance(current, dict) else None
        if current_status in PROTECTED_STATUSES and current_value is not None:
            merged[name] = current
            continue
        if current != proposal:
            changed = True
        merged[name] = proposal
    for key, value in existing.items():
        merged.setdefault(key, value)
    return merged, changed


@dataclass(frozen=True)
class ExtractionOutcome:
    extraction: InquiryExtraction | None
    error_code: str | None
    run: LLMRun


class ExtractionService:
    def __init__(self, provider: LLMProvider, run_repository: LLMRunRepository):
        self._provider = provider
        self._runs = run_repository

    async def extract(self, *, inquiry_text: str, inquiry_id: UUID | None = None) -> ExtractionOutcome:
        config = PURPOSE_CONFIGS["inquiry_extraction"]
        messages = [
            Message(role=MessageRole.SYSTEM, content=config.system_prompt),
            Message(role=MessageRole.USER, content=inquiry_text.strip()),
        ]
        started = time.perf_counter()
        extraction: InquiryExtraction | None = None
        error_code: str | None = None
        usage = None
        repair_used = False
        attempts = 0
        provider_latency_ms: int | None = None
        try:
            result = await self._provider.generate_structured(
                purpose=config.purpose,
                messages=messages,
                output_schema=InquiryExtraction,
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )
            extraction = result.data
            usage = result.usage
            repair_used = result.repair_used
            attempts = result.attempts
            provider_latency_ms = result.latency_ms
        except ProviderError as exc:
            error_code = exc.code.value
            attempts = int(exc.details.get("attempts") or 1)
        if provider_latency_ms is None:
            provider_latency_ms = int((time.perf_counter() - started) * 1000)

        run = LLMRun(
            purpose=config.purpose,
            provider_code="deepseek",
            model=config.model,
            status="SUCCESS" if error_code is None else "PROVIDER_ERROR",
            error_code=error_code,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=provider_latency_ms,
            input_hash=input_hash(inquiry_text),
            inquiry_id=inquiry_id,
            repair_used=repair_used,
            attempts=attempts,
        )
        self._runs.add(run)
        return ExtractionOutcome(extraction=extraction, error_code=error_code, run=run)
