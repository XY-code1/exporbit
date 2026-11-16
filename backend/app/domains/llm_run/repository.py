from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.llm_run.models import LLMRun


class LLMRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, run: LLMRun) -> LLMRun:
        self.session.add(run)
        self.session.flush()
        return run

    def get(self, run_id: UUID) -> LLMRun | None:
        return self.session.scalar(select(LLMRun).where(LLMRun.id == run_id))
