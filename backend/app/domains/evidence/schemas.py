from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ProviderModeValue = Literal["LIVE", "MANUAL", "DEMO", "PLANNED"]
SourceCategoryValue = Literal["CUSTOMER_INQUIRY", "ENTERPRISE", "ZHIHU", "OFFICIAL", "OVERSEAS"]
InformationStatus = Literal["CONFIRMED", "INFERRED", "NEEDS_CONFIRMATION", "INSUFFICIENT_DATA", "UNAVAILABLE"]
SupportType = Literal["SUPPORTS", "CONTRADICTS", "CONTEXT"]


class ProviderRead(BaseModel):
    code: str
    category: SourceCategoryValue | None
    display_name: str
    mode: ProviderModeValue
    enabled: bool
    last_health_status: str | None


class ProviderList(BaseModel):
    items: list[ProviderRead]


class EvidenceRead(BaseModel):
    id: UUID
    inquiry_id: UUID
    provider_code: str | None
    source_category: SourceCategoryValue
    provider_mode: ProviderModeValue
    is_demo: bool
    title: str
    canonical_url: str | None
    captured_text: str
    content_hash: str
    snapshot_verified: bool
    source_published_at: datetime | None
    captured_at: datetime
    availability_status: Literal["AVAILABLE", "UNAVAILABLE"]
    credibility_status: InformationStatus
    captured_by: str | None
    usage_note: str | None


class EvidenceList(BaseModel):
    items: list[EvidenceRead]


class EvidenceInsightLink(BaseModel):
    insight_id: UUID
    statement: str
    status: InformationStatus
    support_type: SupportType


class EvidenceDetail(EvidenceRead):
    insights: list[EvidenceInsightLink]


class EvidenceCaptureRequest(BaseModel):
    kind: Literal["MANUAL", "PROVIDER"] = "MANUAL"
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=100_000)
    canonical_url: str | None = Field(default=None, max_length=500)
    source_category: SourceCategoryValue = "CUSTOMER_INQUIRY"
    captured_by: str | None = Field(default=None, max_length=80)
    source_published_at: datetime | None = None
    usage_note: str | None = Field(default=None, max_length=500)
    provider_code: str | None = Field(default=None, max_length=64)
    query: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def require_kind_fields(self):
        if self.kind == "MANUAL":
            if not self.title or not self.title.strip():
                raise ValueError("title is required for manual evidence")
            if not self.content or not self.content.strip():
                raise ValueError("content is required for manual evidence")
        elif not self.provider_code:
            raise ValueError("provider_code is required for provider capture")
        return self


class EvidenceSaveResponse(BaseModel):
    status: Literal["CAPTURED", "UNAVAILABLE"]
    provider_code: str
    provider_mode: ProviderModeValue
    evidence: EvidenceRead | None = None
    error_code: str | None = None


class InsightEvidenceLinkInput(BaseModel):
    evidence_id: UUID
    support_type: SupportType = "SUPPORTS"


class InsightEvidenceLinkRead(BaseModel):
    evidence_id: UUID
    support_type: SupportType


class InsightCreate(BaseModel):
    statement: str = Field(min_length=1, max_length=5_000)
    status: InformationStatus = "INFERRED"
    evidence_links: list[InsightEvidenceLinkInput] = Field(min_length=1, max_length=50)


class InsightRead(BaseModel):
    id: UUID
    inquiry_id: UUID
    statement: str
    status: InformationStatus
    origin: Literal["AI", "HUMAN"]
    revision: int
    created_at: datetime
    updated_at: datetime
    evidence_links: list[InsightEvidenceLinkRead]


class InsightList(BaseModel):
    items: list[InsightRead]


class EvidenceProvenanceRead(BaseModel):
    evidence_id: UUID
    support_type: SupportType
    title: str
    canonical_url: str | None
    provider_code: str | None
    provider_mode: ProviderModeValue
    source_category: SourceCategoryValue
    is_demo: bool
    availability_status: Literal["AVAILABLE", "UNAVAILABLE"]
    captured_at: datetime
    source_published_at: datetime | None
    content_hash: str
    snapshot_verified: bool
    snapshot_chars: int
    snapshot_text: str


class InsightProvenanceRead(BaseModel):
    insight_id: UUID
    inquiry_id: UUID
    statement: str
    status: InformationStatus
    origin: Literal["AI", "HUMAN"]
    revision: int
    evidence: list[EvidenceProvenanceRead]
