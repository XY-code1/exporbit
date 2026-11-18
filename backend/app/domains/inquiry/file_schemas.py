from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.inquiry.schemas import SourceType


class InquiryFileImportItem(BaseModel):
    file_id: UUID
    inquiry_id: UUID | None
    original_name: str
    media_type: str
    byte_size: int
    sha256: str | None
    parse_status: Literal["SUCCESS", "FAILED"]
    source_type: SourceType | None = None
    subject: str | None = None
    preview_text: str | None = None
    page_count: int = 0
    attachments: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class InquiryFileImportBatch(BaseModel):
    items: list[InquiryFileImportItem]
