"""PDF parsing: text layer first, per-page OCR fallback for scanned pages."""
from __future__ import annotations

import io

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfminer.pdfparser import PDFSyntaxError
from pypdf import PdfReader

from app.providers.documents.contracts import (
    MAX_PDF_PAGES,
    OCR_MIN_TEXT_CHARS,
    PageText,
    ParsedDocument,
    ParseError,
    ParseErrorCode,
)
from app.providers.documents.ocr import OcrEngine

OCR_RENDER_DPI = 200


def parse_pdf(filename: str, data: bytes, ocr: OcrEngine, content_type: str | None = None) -> ParsedDocument:
    try:
        if PdfReader(io.BytesIO(data)).is_encrypted:
            raise ParseError(ParseErrorCode.ENCRYPTED, "PDF is password protected")
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "PDF header cannot be read", {"type": type(exc).__name__}) from exc

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise ParseError(ParseErrorCode.TOO_MANY_PAGES, "PDF exceeds page limit", {"pages": len(pdf.pages)})
            pages: list[PageText] = []
            warnings: list[str] = []
            ocr_pages = 0
            for index, page in enumerate(pdf.pages, start=1):
                try:
                    text = (page.extract_text() or "").strip()
                except Exception:
                    text = ""
                if len("".join(text.split())) < OCR_MIN_TEXT_CHARS:
                    if not ocr.available:
                        warnings.append(f"page {index}: no text layer and OCR unavailable")
                        pages.append(PageText(index, text, "text_layer"))
                        continue
                    text = _ocr_page(page, ocr)
                    ocr_pages += 1
                    pages.append(PageText(index, text, "ocr"))
                else:
                    pages.append(PageText(index, text, "text_layer"))
    except ParseError:
        raise
    except PDFPasswordIncorrect as exc:
        raise ParseError(ParseErrorCode.ENCRYPTED, "PDF is password protected") from exc
    except (PDFSyntaxError, ValueError, OSError) as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "PDF cannot be parsed", {"type": type(exc).__name__}) from exc
    except Exception as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "PDF cannot be parsed", {"type": type(exc).__name__}) from exc

    if ocr_pages and not any(page.text.strip() for page in pages):
        raise ParseError(ParseErrorCode.EMPTY_TEXT, "scanned PDF produced no OCR text", {"pages": len(pages)})
    if not any(page.text.strip() for page in pages):
        raise ParseError(ParseErrorCode.EMPTY_TEXT, "PDF has no extractable text", {"pages": len(pages)})
    if ocr_pages:
        warnings.append(f"ocr_fallback_pages: {ocr_pages}")
    return ParsedDocument(filename=filename, format="pdf", pages=tuple(pages), warnings=tuple(warnings))


def _ocr_page(page, ocr: OcrEngine) -> str:
    try:
        image = page.to_image(resolution=OCR_RENDER_DPI).original
    except Exception as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "PDF page cannot be rendered", {"type": type(exc).__name__}) from exc
    text, _ = ocr.extract(image)
    return text.strip()
