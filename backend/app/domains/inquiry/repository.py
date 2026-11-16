from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.domains.inquiry.models import Inquiry


class InquiryRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, inquiry: Inquiry) -> Inquiry:
        self.session.add(inquiry)
        self.session.flush()
        return inquiry

    def get(self, inquiry_id: UUID) -> Inquiry | None:
        return self.session.scalar(select(Inquiry).options(joinedload(Inquiry.customer)).where(Inquiry.id == inquiry_id))

    def list(self, query: str | None, status: str | None, limit: int) -> list[Inquiry]:
        stmt = select(Inquiry).options(joinedload(Inquiry.customer)).order_by(Inquiry.updated_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Inquiry.workflow_status == status)
        if query:
            term = f"%{query}%"
            stmt = stmt.where(or_(Inquiry.subject.ilike(term), Inquiry.raw_text.ilike(term)))
        return list(self.session.scalars(stmt).unique())

