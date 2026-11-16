from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal["TEXT", "PDF", "IMAGE", "EML"]
WorkflowStatus = Literal["NEW", "ANALYZING", "NEEDS_INFORMATION", "READY_TO_REPLY", "COMPLETED", "FAILED"]


class InquiryCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    raw_text: str = Field(min_length=10, max_length=100_000)
    source_type: SourceType = "TEXT"
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("subject", "raw_text", "customer_name")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class InquiryUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    workflow_status: WorkflowStatus | None = None


class InquiryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    customer_id: UUID | None
    customer_name: str | None = None
    subject: str
    raw_text: str
    source_type: SourceType
    workflow_status: WorkflowStatus
    extracted_fields: dict
    revision: int
    created_at: datetime
    updated_at: datetime


class InquiryList(BaseModel):
    items: list[InquiryRead]
    next_cursor: str | None = None

