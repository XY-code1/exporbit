from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.inquiry.file_models import InquiryFile
from app.domains.inquiry.file_schemas import InquiryFileImportItem
from app.domains.inquiry.models import Inquiry
from app.providers.documents.contracts import MAX_FILE_BYTES, ParseError, ParseErrorCode, ParsedDocument
from app.providers.documents.dispatcher import parse_document

logger = logging.getLogger(__name__)
MAX_IMPORT_FILES = 10
PREVIEW_TEXT_LIMIT = 1200
_SUPPORTED_SOURCE_TYPES = {"pdf": "PDF", "image": "IMAGE", "eml": "EML"}


@dataclass(frozen=True)
class IncomingFile:
    filename: str
    content_type: str | None
    byte_size: int
    data: bytes | None


def safe_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/")
    basename = PurePosixPath(normalized).name
    basename = "".join(char for char in basename if char.isprintable() and char not in "\x00")
    basename = basename.strip().strip(".")
    return (basename or "upload")[:255]


def _to_json(document: ParsedDocument) -> dict:
    return {
        "filename": document.filename,
        "format": document.format,
        "pages": [
            {"page_number": page.page_number, "text": page.text, "source": page.source}
            for page in document.pages
        ],
        "attachments": [
            {
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "parsed": item.parsed,
                "skip_reason": item.skip_reason,
            }
            for item in document.attachments
        ],
        "warnings": list(document.warnings),
    }


def _preview(document_data: dict | None) -> tuple[str | None, int, list[dict], list[str]]:
    if not document_data:
        return None, 0, [], []
    pages = document_data.get("pages", [])
    text = "\n".join(page.get("text", "") for page in pages if page.get("text"))
    return text[:PREVIEW_TEXT_LIMIT], len(pages), document_data.get("attachments", []), document_data.get("warnings", [])


def _make_item(record: InquiryFile, source_type: str | None = None, subject: str | None = None) -> InquiryFileImportItem:
    preview, page_count, attachments, warnings = _preview(record.parsed_document)
    return InquiryFileImportItem(
        file_id=record.id,
        inquiry_id=record.inquiry_id,
        original_name=record.original_name,
        media_type=record.media_type,
        byte_size=record.byte_size,
        sha256=record.sha256,
        parse_status=record.parse_status,
        source_type=source_type,
        subject=subject,
        preview_text=preview,
        page_count=page_count,
        attachments=attachments,
        warnings=warnings,
        error_code=record.error_code,
        error_message=record.error_message,
        created_at=record.created_at,
    )


class InquiryFileImportService:
    def __init__(self, session: Session, storage_dir: Path) -> None:
        self.session = session
        self.storage_dir = Path(storage_dir)

    def import_files(self, incoming_files: Iterable[IncomingFile]) -> list[InquiryFileImportItem]:
        created_paths: list[Path] = []
        response_items: list[InquiryFileImportItem] = []
        try:
            for incoming in incoming_files:
                if len(response_items) >= MAX_IMPORT_FILES:
                    raise AppError("TOO_MANY_FILES", f"A maximum of {MAX_IMPORT_FILES} files can be imported at once", 422)
                record, parent_record, saved_path, source_type, subject = self._process_one(incoming)
                if saved_path is not None:
                    created_paths.append(saved_path)
                # Flush into the existing transaction, then detach only objects
                # created for this file so parsed page text cannot accumulate.
                self.session.flush()
                self.session.refresh(record, attribute_names=["created_at"])
                response_items.append(_make_item(record, source_type, subject))
                if parent_record is not None:
                    self.session.expunge(parent_record)
                self.session.expunge(record)
                # Release the current upload buffer before asking a lazy source
                # to read the next file, keeping raw input memory bounded to one file.
                del incoming, record, parent_record
            if not response_items:
                raise AppError("FILES_REQUIRED", "At least one file is required", 422)
            self.session.commit()
        except Exception:
            self.session.rollback()
            for saved_path in created_paths:
                try:
                    saved_path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove uncommitted inquiry upload")
            raise
        return response_items

    def list_files(self, inquiry_id: uuid.UUID) -> list[InquiryFileImportItem]:
        if self.session.scalar(select(Inquiry.id).where(Inquiry.id == inquiry_id)) is None:
            raise AppError("INQUIRY_NOT_FOUND", "Inquiry not found", 404, {"inquiry_id": str(inquiry_id)})
        records = self.session.scalars(
            select(InquiryFile).where(InquiryFile.inquiry_id == inquiry_id).order_by(InquiryFile.created_at, InquiryFile.id)
        ).all()
        return [_make_item(record) for record in records]

    def _process_one(
        self, incoming: IncomingFile
    ) -> tuple[InquiryFile, Inquiry | None, Path | None, str | None, str | None]:
        original_name = safe_filename(incoming.filename)
        media_type = (incoming.content_type or "application/octet-stream")[:255]
        data = incoming.data
        size = max(incoming.byte_size, len(data) if data is not None else 0)
        file_id = uuid.uuid4()
        sha256 = hashlib.sha256(data).hexdigest() if data is not None else None
        storage_key: str | None = None
        saved_path: Path | None = None
        parsed_data: dict | None = None
        inquiry_id: uuid.UUID | None = None
        parent_record: Inquiry | None = None
        source_type: str | None = None
        subject: str | None = None
        parse_status = "FAILED"
        error_code: str | None = None
        error_message: str | None = None

        if data is None or size > MAX_FILE_BYTES:
            error_code = ParseErrorCode.FILE_TOO_LARGE.value
            error_message = f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit"
        else:
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                storage_key = uuid.uuid4().hex
                final_path = self.storage_dir / storage_key
                temp_path = self.storage_dir / f".{storage_key}.tmp"
                with temp_path.open("xb") as stored_file:
                    stored_file.write(data)
                    stored_file.flush()
                    os.fsync(stored_file.fileno())
                os.replace(temp_path, final_path)
                saved_path = final_path

                document = parse_document(original_name, data, media_type)
                raw_text = document.text.strip()
                if len(raw_text) < 10:
                    raise ParseError(ParseErrorCode.EMPTY_TEXT, "parsed text is too short to create an inquiry")

                parsed_data = _to_json(document)
                source_type = _SUPPORTED_SOURCE_TYPES[document.format]
                inquiry_id = uuid.uuid4()
                subject = Path(original_name).stem.strip()[:300] or "文件询盘"
                parent_record = Inquiry(
                    id=inquiry_id,
                    subject=subject,
                    raw_text=raw_text,
                    source_type=source_type,
                    workflow_status="NEW",
                    extracted_fields={},
                    content_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                )
                self.session.add(parent_record)
                parse_status = "SUCCESS"
            except ParseError as exc:
                error_code = exc.code.value
                error_message = str(exc)
            except OSError:
                if saved_path is None:
                    error_code = "STORAGE_ERROR"
                    error_message = "The original file could not be saved; please retry the upload"
                    if storage_key:
                        try:
                            (self.storage_dir / f".{storage_key}.tmp").unlink(missing_ok=True)
                        except OSError:
                            logger.exception("Could not remove incomplete inquiry upload")
                else:
                    error_code = "PARSER_ERROR"
                    error_message = "The file could not be parsed; try another file or paste its text"
            except Exception:
                logger.exception("Unexpected error while parsing inquiry upload %s", original_name)
                error_code = "PARSER_ERROR"
                error_message = "The file could not be parsed; try another file or paste its text"

        if inquiry_id is not None:
            # Scalar FK IDs alone do not tell the ORM's unit of work to insert
            # the inquiry before its file. Flush the parent within this batch's
            # transaction; do not commit it separately or alter the FK.
            try:
                self.session.flush()
            except Exception:
                if saved_path is not None:
                    try:
                        saved_path.unlink(missing_ok=True)
                    except OSError:
                        logger.exception("Could not remove uncommitted inquiry upload")
                raise

        record = InquiryFile(
            id=file_id,
            inquiry_id=inquiry_id,
            original_name=original_name,
            media_type=media_type,
            byte_size=size,
            sha256=sha256,
            storage_key=storage_key if saved_path is not None else None,
            parse_status=parse_status,
            parsed_document=parsed_data,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(record)
        return record, parent_record, saved_path, source_type, subject
