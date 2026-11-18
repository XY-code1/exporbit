import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.application.inquiry_file_import_service import IncomingFile, InquiryFileImportService, MAX_IMPORT_FILES
from app.application.inquiry_service import InquiryService
from app.application.inquiry_extraction_service import InquiryExtractionService
from app.core.config import settings
from app.core.errors import AppError
from app.domains.inquiry.file_schemas import InquiryFileImportBatch
from app.domains.inquiry.schemas import InquiryCreate, InquiryList, InquiryRead, InquiryUpdate, WorkflowStatus
from app.domains.extraction.v2_schemas import ExtractionHistoryResponse, ExtractionResponse
from app.infrastructure.database import get_session
from app.providers.deepseek import DeepSeekProvider
from app.providers.documents.contracts import MAX_FILE_BYTES

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


@router.post("/import", response_model=InquiryFileImportBatch, status_code=status.HTTP_201_CREATED)
def import_inquiry_files(files: list[UploadFile] = File(...), session: Session = Depends(get_session)):
    if not files:
        raise AppError("FILES_REQUIRED", "At least one file is required", 422)
    if len(files) > MAX_IMPORT_FILES:
        raise AppError("TOO_MANY_FILES", f"A maximum of {MAX_IMPORT_FILES} files can be imported at once", 422)

    # Starlette keeps small multipart uploads in memory by default. Spill every
    # upload to its temporary file before processing the batch sequentially.
    for upload in files:
        rollover = getattr(upload.file, "rollover", None)
        if callable(rollover):
            rollover()

    def iter_incoming_files():
        for upload in files:
            upload.file.seek(0, os.SEEK_END)
            byte_size = max(0, upload.file.tell())
            upload.file.seek(0)
            data = None if byte_size > MAX_FILE_BYTES else upload.file.read(MAX_FILE_BYTES + 1)
            yield IncomingFile(
                filename=upload.filename or "upload",
                content_type=upload.content_type,
                byte_size=byte_size,
                data=data,
            )
            # Do not keep a reference to the prior file while reading the next.
            del data

    items = InquiryFileImportService(session, settings.file_storage_path).import_files(iter_incoming_files())
    return InquiryFileImportBatch(items=items)


@router.get("", response_model=InquiryList)
def list_inquiries(
    q: str | None = Query(default=None, max_length=200),
    workflow_status: WorkflowStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return InquiryList(items=InquiryService(session).list(q, workflow_status, limit))


@router.get("/{inquiry_id}/files", response_model=InquiryFileImportBatch)
def list_inquiry_files(inquiry_id: UUID, session: Session = Depends(get_session)):
    items = InquiryFileImportService(session, settings.file_storage_path).list_files(inquiry_id)
    return InquiryFileImportBatch(items=items)


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


@router.get("/{inquiry_id}/extractions/latest", response_model=ExtractionResponse | None)
def get_latest_inquiry_extraction(inquiry_id: UUID, session: Session = Depends(get_session)):
    return InquiryExtractionService(session).get_latest(inquiry_id)


@router.get("/{inquiry_id}/extractions", response_model=ExtractionHistoryResponse)
def list_inquiry_extractions(inquiry_id: UUID, session: Session = Depends(get_session)):
    items = InquiryExtractionService(session).list_history(inquiry_id)
    return ExtractionHistoryResponse(items=items, total=len(items))


@router.get("/{inquiry_id}/extractions/{extraction_id}", response_model=ExtractionResponse)
def get_inquiry_extraction(
    inquiry_id: UUID,
    extraction_id: UUID,
    session: Session = Depends(get_session),
):
    return InquiryExtractionService(session).get_record(inquiry_id, extraction_id)


@router.post("/{inquiry_id}/extract", response_model=ExtractionResponse)
async def extract_inquiry(
    inquiry_id: UUID,
    session: Session = Depends(get_session),
    provider=Depends(get_llm_provider),
):
    return await InquiryExtractionService(session, provider).extract(inquiry_id)
