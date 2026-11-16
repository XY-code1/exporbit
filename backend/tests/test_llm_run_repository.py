"""LLMRun persistence roundtrip against the test PostgreSQL database."""
import uuid

import pytest

from app.domains.llm_run.models import LLMRun
from app.domains.llm_run.repository import LLMRunRepository
from app.infrastructure.database import SessionLocal
from tests.conftest import requires_db

pytestmark = requires_db


def _make_run(**overrides) -> LLMRun:
    fields = dict(
        purpose="inquiry_extraction",
        provider_code="deepseek",
        model="deepseek-chat",
        status="SUCCESS",
        error_code=None,
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        latency_ms=1250,
        input_hash="a" * 64,
        inquiry_id=None,
        repair_used=False,
        attempts=1,
    )
    fields.update(overrides)
    return LLMRun(**fields)


def test_llm_run_roundtrip():
    run = _make_run()
    with SessionLocal() as session:
        repo = LLMRunRepository(session)
        repo.add(run)
        session.commit()
        run_id = run.id
    assert run_id is not None
    with SessionLocal() as session:
        loaded = LLMRunRepository(session).get(run_id)
        assert loaded is not None
        assert loaded.purpose == "inquiry_extraction"
        assert loaded.model == "deepseek-chat"
        assert loaded.status == "SUCCESS"
        assert loaded.total_tokens == 200
        assert loaded.latency_ms == 1250
        assert loaded.input_hash == "a" * 64
        assert loaded.repair_used is False


def test_failed_run_persists_error_code_and_zero_usage():
    run = _make_run(
        status="PROVIDER_ERROR",
        error_code="PROVIDER_TIMEOUT",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        attempts=3,
    )
    with SessionLocal() as session:
        repo = LLMRunRepository(session)
        repo.add(run)
        session.commit()
        run_id = run.id
    with SessionLocal() as session:
        loaded = LLMRunRepository(session).get(run_id)
        assert loaded.error_code == "PROVIDER_TIMEOUT"
        assert loaded.attempts == 3
        assert loaded.total_tokens == 0


def test_missing_run_returns_none():
    with SessionLocal() as session:
        assert LLMRunRepository(session).get(uuid.uuid4()) is None
