from sqlalchemy.orm import Session

from app.domains.extraction.models import InquiryExtractionRecord


class InquiryExtractionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, record: InquiryExtractionRecord) -> InquiryExtractionRecord:
        self.session.add(record)
        self.session.flush()
        return record
