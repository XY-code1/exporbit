"""Format detection and dispatch for document parsing."""
from __future__ import annotations

import os

from app.providers.documents.contracts import (
    MAX_FILE_BYTES,
    ParsedDocument,
    ParseError,
    ParseErrorCode,
)
from app.providers.documents.eml import parse_eml
from app.providers.documents.images import parse_image
from app.providers.documents.ocr import OcrEngine, RapidOcrEngine
from app.providers.documents.pdf import parse_pdf

_EXTENSION_FORMATS = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".eml": "eml",
}

_MAGIC_FORMATS = (
    (b"%PDF-", "pdf"),
    (b"\xff\xd8\xff", "image"),
    (b"\x89PNG\r\n\x1a\n", "image"),
    (b"II*\x00", "image"),
    (b"MM\x00*", "image"),
    (b"BM", "image"),
)

_default_ocr = RapidOcrEngine()


def detect_format(filename: str, data: bytes) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension in _EXTENSION_FORMATS:
        return _EXTENSION_FORMATS[extension]
    for magic, fmt in _MAGIC_FORMATS:
        if data.startswith(magic):
            return fmt
    raise ParseError(ParseErrorCode.UNSUPPORTED_FORMAT, "no parser for this file type", {"extension": extension or None})


def parse_document(
    filename: str,
    data: bytes,
    content_type: str | None = None,
    ocr: OcrEngine | None = None,
) -> ParsedDocument:
    if len(data) > MAX_FILE_BYTES:
        raise ParseError(ParseErrorCode.FILE_TOO_LARGE, "file exceeds size limit", {"bytes": len(data)})
    if not data:
        raise ParseError(ParseErrorCode.CORRUPTED, "file is empty")
    fmt = detect_format(filename, data)
    engine = ocr or _default_ocr
    if fmt == "pdf":
        return parse_pdf(filename, data, engine, content_type)
    if fmt == "image":
        return parse_image(filename, data, engine, content_type)
    return parse_eml(
        filename,
        data,
        lambda name, payload, ctype: parse_document(name, payload, ctype, ocr=engine),
    )
