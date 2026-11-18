from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.extraction.models import InquiryExtractionRecord


class InquiryExtractionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, record: InquiryExtractionRecord) -> InquiryExtractionRecord:
        self.session.add(record)
        self.session.flush()
        return record

    def get_latest(self, inquiry_id: UUID) -> InquiryExtractionRecord | None:
        statement = (
            select(InquiryExtractionRecord)
            .where(InquiryExtractionRecord.inquiry_id == inquiry_id)
            .order_by(InquiryExtractionRecord.created_at.desc(), InquiryExtractionRecord.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def list_for_inquiry(self, inquiry_id: UUID) -> list[InquiryExtractionRecord]:
        statement = (
            select(InquiryExtractionRecord)
            .where(InquiryExtractionRecord.inquiry_id == inquiry_id)
            .order_by(InquiryExtractionRecord.created_at.desc(), InquiryExtractionRecord.id.desc())
        )
        return list(self.session.scalars(statement).all())

    def get(self, inquiry_id: UUID, extraction_id: UUID) -> InquiryExtractionRecord | None:
        statement = select(InquiryExtractionRecord).where(
            InquiryExtractionRecord.inquiry_id == inquiry_id,
            InquiryExtractionRecord.id == extraction_id,
        )
        return self.session.scalar(statement)
