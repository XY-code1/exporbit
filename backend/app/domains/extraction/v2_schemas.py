"""POC-02 normalized inquiry extraction contract.

Every business value carries an explicit information status. Missing values are
represented by null, never invented placeholders.
"""
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InformationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


T = TypeVar("T")


class StatusValue(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    value: T | None = None
    status: InformationStatus = InformationStatus.INSUFFICIENT_DATA
    evidence: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def normalize_missing(self):
        if self.value is None:
            self.status = InformationStatus.INSUFFICIENT_DATA
            self.evidence = None
        elif self.status is InformationStatus.INSUFFICIENT_DATA:
            self.status = InformationStatus.NEEDS_CONFIRMATION
        return self


class CustomerInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_name: StatusValue[str]
    company_name: StatusValue[str]
    email: StatusValue[str]
    country: StatusValue[str]


class ProductRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_type: StatusValue[str]
    product_description: StatusValue[str]
    quantity: StatusValue[float]
    quantity_unit: StatusValue[str]
    specifications: StatusValue[dict[str, str]]
    customization_requirements: StatusValue[list[str]]
    certification_requirements: StatusValue[list[str]]


class BusinessRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_market: StatusValue[str]
    expected_delivery: StatusValue[str]
    target_price: StatusValue[str]
    purchasing_intent: StatusValue[str]


class StructuredInquiryExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer: CustomerInformation
    products: list[ProductRequirement] = Field(min_length=1, max_length=20)
    business: BusinessRequirements
    missing_fields: list[str]
    clarification_questions: list[str]


class ExtractionResponse(BaseModel):
    extraction_id: str
    inquiry_id: str
    structured_data: StructuredInquiryExtraction | None
    extraction_status: str
    provider: str
    model: str
    error_code: str | None = None
    created_at: str
