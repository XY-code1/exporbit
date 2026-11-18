import hashlib
import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.extraction.models import InquiryExtractionRecord
from app.domains.extraction.repository import InquiryExtractionRepository
from app.domains.extraction.v2_prompt import EXTRACTION_V2_PROMPT
from app.domains.extraction.v2_schemas import ExtractionResponse, StructuredInquiryExtraction
from app.domains.inquiry.repository import InquiryRepository
from app.domains.llm_run.models import LLMRun
from app.domains.llm_run.repository import LLMRunRepository
from app.providers.contracts import LLMProvider, Message, MessageRole, ProviderError


class InquiryExtractionService:
    def __init__(self, session: Session, provider: LLMProvider | None = None):
        self.session = session
        self.provider = provider
        self.inquiries = InquiryRepository(session)
        self.extractions = InquiryExtractionRepository(session)
        self.runs = LLMRunRepository(session)

    @staticmethod
    def _serialize(record: InquiryExtractionRecord) -> ExtractionResponse:
        return ExtractionResponse(
            extraction_id=str(record.id),
            inquiry_id=str(record.inquiry_id),
            structured_data=(
                StructuredInquiryExtraction.model_validate(record.structured_data)
                if record.structured_data is not None
                else None
            ),
            extraction_status=record.status,
            provider=record.provider_code,
            model=record.model,
            error_code=record.error_code,
            created_at=record.created_at.isoformat(),
        )

    def get_latest(self, inquiry_id: UUID) -> ExtractionResponse | None:
        inquiry = self.inquiries.get(inquiry_id)
        if inquiry is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        record = self.extractions.get_latest(inquiry_id)
        return self._serialize(record) if record is not None else None

    def list_history(self, inquiry_id: UUID) -> list[ExtractionResponse]:
        inquiry = self.inquiries.get(inquiry_id)
        if inquiry is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        return [self._serialize(record) for record in self.extractions.list_for_inquiry(inquiry_id)]

    def get_record(self, inquiry_id: UUID, extraction_id: UUID) -> ExtractionResponse:
        inquiry = self.inquiries.get(inquiry_id)
        if inquiry is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        record = self.extractions.get(inquiry_id, extraction_id)
        if record is None:
            raise AppError(
                "EXTRACTION_NOT_FOUND",
                "Extraction record not found",
                404,
                {"inquiry_id": str(inquiry_id), "extraction_id": str(extraction_id)},
            )
        return self._serialize(record)

    async def extract(self, inquiry_id: UUID) -> ExtractionResponse:
        inquiry = self.inquiries.get(inquiry_id)
        if inquiry is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        if self.provider is None:
            raise AppError("PROVIDER_UNAVAILABLE", "Extraction provider is unavailable", 503)
        started = time.perf_counter()
        data = None
        error_code = None
        usage = None
        attempts = 1
        model = getattr(self.provider, "model_name", "deepseek-chat")
        try:
            result = await self.provider.generate_structured(
                purpose="inquiry_extraction_v2",
                messages=[
                    Message(role=MessageRole.SYSTEM, content=EXTRACTION_V2_PROMPT),
                    Message(role=MessageRole.USER, content=inquiry.raw_text),
                ],
                output_schema=StructuredInquiryExtraction,
                model=model,
                temperature=0.0,
                max_tokens=3000,
            )
            data = result.data
            usage = result.usage
            attempts = result.attempts
            model = result.model
        except ProviderError as exc:
            error_code = exc.code.value
            attempts = int(exc.details.get("attempts") or 1)

        run = self.runs.add(LLMRun(
            purpose="inquiry_extraction_v2", provider_code="deepseek", model=model,
            status="SUCCESS" if data else "PROVIDER_ERROR", error_code=error_code,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            input_hash=hashlib.sha256(inquiry.raw_text.encode()).hexdigest(),
            inquiry_id=inquiry.id, repair_used=False, attempts=attempts,
        ))
        record = self.extractions.add(InquiryExtractionRecord(
            inquiry_id=inquiry.id, llm_run_id=run.id,
            structured_data=data.model_dump(mode="json") if data else None,
            status="SUCCESS" if data else "FAILED", provider_code="deepseek",
            model=model, error_code=error_code,
        ))
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)
