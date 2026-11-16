"""Image parsing: EXIF orientation correction, size guard, OCR with rotation search."""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.providers.documents.contracts import (
    MAX_IMAGE_DIMENSION,
    OCR_MIN_TEXT_CHARS,
    PageText,
    ParsedDocument,
    ParseError,
    ParseErrorCode,
)
from app.providers.documents.ocr import LOW_CONFIDENCE, OcrEngine


def _prepare(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    return image


def parse_image(filename: str, data: bytes, ocr: OcrEngine, content_type: str | None = None) -> ParsedDocument:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ParseError(ParseErrorCode.CORRUPTED, "image cannot be decoded", {"type": type(exc).__name__}) from exc

    image = _prepare(image)
    if not ocr.available:
        raise ParseError(ParseErrorCode.OCR_UNAVAILABLE, "OCR engine not installed")

    text, confidence = ocr.extract(image)
    warnings: list[str] = []
    best = (text, confidence)
    if confidence < LOW_CONFIDENCE or len(text.strip()) < OCR_MIN_TEXT_CHARS:
        # Photos without EXIF orientation are common; try right-angles and keep the best read.
        for angle in (90, 180, 270):
            candidate_text, candidate_conf = ocr.extract(image.rotate(angle, expand=True))
            if (candidate_conf, len(candidate_text)) > (best[1], len(best[0])):
                best = (candidate_text, candidate_conf)
        if best != (text, confidence):
            warnings.append(f"rotated_image_detected: tried 90/180/270 (best confidence {best[1]:.2f})")

    text = best[0].strip()
    if len(text) < OCR_MIN_TEXT_CHARS:
        raise ParseError(ParseErrorCode.EMPTY_TEXT, "OCR produced no usable text", {"chars": len(text)})
    return ParsedDocument(filename=filename, format="image", pages=(PageText(1, text, "ocr"),), warnings=tuple(warnings))
