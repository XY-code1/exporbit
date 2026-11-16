import hashlib
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.inquiry.models import Customer, Inquiry
from app.domains.inquiry.repository import InquiryRepository
from app.domains.inquiry.schemas import InquiryCreate, InquiryRead, InquiryUpdate


def to_read(model: Inquiry) -> InquiryRead:
    result = InquiryRead.model_validate(model)
    return result.model_copy(update={"customer_name": model.customer.legal_name if model.customer else None})


class InquiryService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = InquiryRepository(session)

    def create(self, data: InquiryCreate) -> InquiryRead:
        customer = Customer(legal_name=data.customer_name) if data.customer_name else None
        if customer:
            self.session.add(customer)
            self.session.flush()
        inquiry = Inquiry(
            customer_id=customer.id if customer else None,
            customer=customer,
            subject=data.subject,
            raw_text=data.raw_text,
            source_type=data.source_type,
            workflow_status="NEW",
            extracted_fields={},
            content_hash=hashlib.sha256(data.raw_text.encode("utf-8")).hexdigest(),
        )
        self.repo.add(inquiry)
        self.session.commit()
        return to_read(inquiry)

    def get(self, inquiry_id: UUID) -> InquiryRead:
        inquiry = self.repo.get(inquiry_id)
        if not inquiry:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        return to_read(inquiry)

    def list(self, query: str | None, status: str | None, limit: int) -> list[InquiryRead]:
        return [to_read(item) for item in self.repo.list(query, status, limit)]

    def update(self, inquiry_id: UUID, data: InquiryUpdate, expected_revision: int) -> InquiryRead:
        values = data.model_dump(exclude_none=True)
        if not values:
            return self.get(inquiry_id)
        values["revision"] = expected_revision + 1
        stmt = update(Inquiry).where(Inquiry.id == inquiry_id, Inquiry.revision == expected_revision).values(**values).returning(Inquiry.id)
        if not self.session.scalar(stmt):
            self.session.rollback()
            if not self.repo.get(inquiry_id):
                raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404)
            raise AppError("REVISION_CONFLICT", "Inquiry was modified by another request", 409, {"expected_revision": expected_revision})
        self.session.commit()
        return self.get(inquiry_id)

