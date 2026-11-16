"""OCR path tests: stub engines for scanning/rotation logic, one real-engine smoke test."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.providers.documents import ParseError, ParseErrorCode, parse_document
from app.providers.documents.ocr import RapidOcrEngine

CORPUS = Path(__file__).resolve().parents[1] / "data" / "poc03_corpus"


def load(name: str) -> bytes:
    return (CORPUS / name).read_bytes()


class StubOcr:
    def __init__(self, text: str = "SCANNED INQUIRY TEXT FROM OCR", confidence: float = 0.9) -> None:
        self.text = text
        self.confidence = confidence
        self.calls = 0

    @property
    def available(self) -> bool:
        return True

    def extract(self, image) -> tuple[str, float]:
        self.calls += 1
        return self.text, self.confidence


class UnavailableOcr:
    available = False

    def extract(self, image) -> tuple[str, float]:
        raise AssertionError("extract must not be called when the engine is unavailable")


class RotationOcr:
    """Poor first read, good read once the image is rotated."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def available(self) -> bool:
        return True

    def extract(self, image) -> tuple[str, float]:
        self.calls += 1
        if self.calls == 1:
            return "upside down", 0.10
        return "quantity 1200 units CIF Hamburg", 0.92


def test_scanned_pdf_falls_back_to_ocr_with_provenance() -> None:
    doc = parse_document("pdf_scan_en_1p.pdf", load("pdf_scan_en_1p.pdf"), ocr=StubOcr())
    assert len(doc.pages) == 1
    assert doc.pages[0].source == "ocr"
    assert doc.pages[0].text.startswith("SCANNED INQUIRY")
    assert doc.used_ocr
    assert "ocr_fallback_pages: 1" in doc.warnings


def test_scanned_pdf_without_ocr_engine_fails_controlled() -> None:
    with pytest.raises(ParseError) as caught:
        parse_document("pdf_scan_en_1p.pdf", load("pdf_scan_en_1p.pdf"), ocr=UnavailableOcr())
    assert caught.value.code is ParseErrorCode.EMPTY_TEXT


def test_image_ocr_happy_path() -> None:
    engine = StubOcr("EXIF-OK-441 quantity 500 units FOB Shenzhen", 0.93)
    doc = parse_document("img_photo_en_exif90.jpg", load("img_photo_en_exif90.jpg"), ocr=engine)
    assert doc.format == "image"
    assert doc.pages[0].source == "ocr"
    assert "EXIF-OK-441" in doc.pages[0].text
    assert engine.calls == 1


def test_unoriented_image_triggers_rotation_search() -> None:
    engine = RotationOcr()
    doc = parse_document("img_rot180_noexif.png", load("img_rot180_noexif.png"), ocr=engine)
    assert "quantity 1200 units" in doc.pages[0].text
    assert any(warning.startswith("rotated_image_detected") for warning in doc.warnings)
    assert engine.calls == 4  # original + 90/180/270


def test_short_ocr_output_is_empty_text() -> None:
    with pytest.raises(ParseError) as caught:
        parse_document("img_rot180_noexif.png", load("img_rot180_noexif.png"), ocr=StubOcr("ab", 0.99))
    assert caught.value.code is ParseErrorCode.EMPTY_TEXT


def test_image_without_ocr_engine_reports_unavailable() -> None:
    with pytest.raises(ParseError) as caught:
        parse_document("img_photo_en_exif90.jpg", load("img_photo_en_exif90.jpg"), ocr=UnavailableOcr())
    assert caught.value.code is ParseErrorCode.OCR_UNAVAILABLE


def test_real_rapidocr_reads_synthetic_photo() -> None:
    engine = RapidOcrEngine()
    if not engine.available:
        pytest.skip("RapidOCR engine is not installed")
    doc = parse_document("img_photo_en_exif90.jpg", load("img_photo_en_exif90.jpg"), ocr=engine)
    assert "EXIF-OK-441" in doc.pages[0].text
    assert "quantity 500 units" in doc.pages[0].text.lower()
