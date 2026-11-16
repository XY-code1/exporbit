"""Document parsing contracts (docs/POC_VALIDATION_PLAN.md, POC-03).

Parsers are provider-side infrastructure: the domain receives a normalized
`ParsedDocument` with page-level provenance and never sees library-specific
types. Every failure is a stable `ParseErrorCode`, mirroring the LLM provider
error taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 2200
OCR_MIN_TEXT_CHARS = 25

EXECUTABLE_EXTENSIONS = frozenset(
    {".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jar", ".scr", ".com", ".pif"}
)
SUPPORTED_ATTACHMENT_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})


class ParseErrorCode(str, Enum):
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    CORRUPTED = "CORRUPTED"
    ENCRYPTED = "ENCRYPTED"
    EMPTY_TEXT = "EMPTY_TEXT"
    OCR_UNAVAILABLE = "OCR_UNAVAILABLE"
    TOO_MANY_PAGES = "TOO_MANY_PAGES"


class ParseError(Exception):
    """Controlled parse failure. `details` must never contain file contents."""

    def __init__(self, code: ParseErrorCode, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class PageText:
    """Text from one provenance unit. `page_number` is 1-based and continues
    across email attachments so `(source, page_number)` stays unambiguous."""

    page_number: int
    text: str
    source: str  # "text_layer" | "ocr" | "email_body" | "attachment:<filename>"


@dataclass(frozen=True)
class AttachmentInfo:
    filename: str
    content_type: str
    size_bytes: int
    parsed: bool = False
    skip_reason: str | None = None  # "executable_blocked" | "unsupported_type" | "too_large" | "nested_email"


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    format: str  # "pdf" | "image" | "eml"
    pages: tuple[PageText, ...]
    attachments: tuple[AttachmentInfo, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages if page.text)

    @property
    def used_ocr(self) -> bool:
        return any(page.source == "ocr" for page in self.pages)


class DocumentParser(Protocol):
    format: str

    def parse(self, filename: str, data: bytes, content_type: str | None = None) -> ParsedDocument: ...
