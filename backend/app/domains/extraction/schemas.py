"""Fixed extraction schema for inquiry snapshot fields.

Every field carries `value`, one of the five global information states, and an
optional verbatim `evidence` quote. States follow docs/INQUIRY_WORKSPACE_SPEC.md:
CONFIRMED / INFERRED / NEEDS_CONFIRMATION / INSUFFICIENT_DATA / UNAVAILABLE.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ABSENT_STATUSES = frozenset({"INSUFFICIENT_DATA", "UNAVAILABLE"})

FIELD_ORDER = (
    "customer_need",
    "quantity",
    "target_market",
    "customization_needs",
    "delivery_timeline",
    "price_terms",
)


class InfoStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNAVAILABLE = "UNAVAILABLE"


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    status: InfoStatus = InfoStatus.INSUFFICIENT_DATA
    evidence: str | None = Field(default=None, max_length=200)

    @field_validator("value", mode="before")
    @classmethod
    def stringify_value(cls, raw):
        if isinstance(raw, bool):
            return str(raw).lower()
        if isinstance(raw, (int, float)):
            return str(raw)
        return raw

    @model_validator(mode="after")
    def coerce_status(self):
        if self.value is None:
            if self.status not in _ABSENT_STATUSES:
                self.status = InfoStatus.INSUFFICIENT_DATA
            self.evidence = None
        elif self.status in _ABSENT_STATUSES:
            self.status = InfoStatus.NEEDS_CONFIRMATION
        return self


class InquiryExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_need: ExtractedField
    quantity: ExtractedField
    target_market: ExtractedField
    customization_needs: ExtractedField
    delivery_timeline: ExtractedField
    price_terms: ExtractedField

    @model_validator(mode="before")
    @classmethod
    def unwrap_fields_wrapper(cls, data):
        # The extraction prompt asks for {"fields": {...}}; unwrap that envelope.
        if isinstance(data, dict) and isinstance(data.get("fields"), dict):
            return data["fields"]
        return data

    def field(self, name: str) -> ExtractedField:
        return getattr(self, name)

    def as_persisted_dict(self) -> dict:
        return {name: self.field(name).model_dump(mode="json") for name in FIELD_ORDER}
