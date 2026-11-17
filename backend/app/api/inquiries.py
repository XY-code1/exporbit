from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.application.inquiry_service import InquiryService
from app.application.inquiry_extraction_service import InquiryExtractionService
from app.core.errors import AppError
from app.domains.inquiry.schemas import InquiryCreate, InquiryList, InquiryRead, InquiryUpdate, WorkflowStatus
from app.domains.extraction.v2_schemas import ExtractionResponse
from app.infrastructure.database import get_session
from app.providers.deepseek import DeepSeekProvider

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


async def get_llm_provider():
    provider = DeepSeekProvider()
    try:
        yield provider
    finally:
        await provider.close()


@router.post("", response_model=InquiryRead, status_code=status.HTTP_201_CREATED)
def create_inquiry(payload: InquiryCreate, session: Session = Depends(get_session)):
    return InquiryService(session).create(payload)


@router.get("", response_model=InquiryList)
def list_inquiries(
    q: str | None = Query(default=None, max_length=200),
    workflow_status: WorkflowStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return InquiryList(items=InquiryService(session).list(q, workflow_status, limit))


@router.get("/{inquiry_id}", response_model=InquiryRead)
def get_inquiry(inquiry_id: UUID, session: Session = Depends(get_session)):
    return InquiryService(session).get(inquiry_id)


@router.patch("/{inquiry_id}", response_model=InquiryRead)
def update_inquiry(
    inquiry_id: UUID,
    payload: InquiryUpdate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    session: Session = Depends(get_session),
):
    if if_match is None or not if_match.isdigit():
        raise AppError("REVISION_REQUIRED", "If-Match revision header is required", 428)
    return InquiryService(session).update(inquiry_id, payload, int(if_match))


@router.post("/{inquiry_id}/extract", response_model=ExtractionResponse)
async def extract_inquiry(
    inquiry_id: UUID,
    session: Session = Depends(get_session),
    provider=Depends(get_llm_provider),
):
    return await InquiryExtractionService(session, provider).extract(inquiry_id)

