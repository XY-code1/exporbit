"""Local OCR engine behind a small interface.

RapidOCR (Apache-2.0, PP-OCR models bundled, onnxruntime CPU) keeps OCR
offline: no cloud calls, no per-page fees and no customer data leaving the
machine. The import is lazy so a missing engine degrades to OCR_UNAVAILABLE
instead of breaking module import.
"""
from __future__ import annotations

import logging
import threading
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)

LOW_CONFIDENCE = 0.65


class OcrEngine(Protocol):
    @property
    def available(self) -> bool: ...

    def extract(self, image: Image.Image) -> tuple[str, float]:
        """Return (text, mean confidence in [0, 1])."""
        ...


class RapidOcrEngine:
    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()
        self._load_error: str | None = None
        self._tried = False

    def _ensure_loaded(self):
        if self._engine is not None or self._load_error is not None:
            return self._engine
        with self._lock:
            if self._engine is not None or self._load_error is not None:
                return self._engine
            if not self._tried:
                self._tried = True
                try:
                    import numpy as np
                    from rapidocr import RapidOCR

                    self._engine = (RapidOCR(), np)
                except Exception as exc:  # pragma: no cover - depends on local install
                    self._load_error = type(exc).__name__
                    logger.warning("OCR engine unavailable: %s", self._load_error)
        return self._engine

    @property
    def available(self) -> bool:
        return self._ensure_loaded() is not None

    def extract(self, image: Image.Image) -> tuple[str, float]:
        loaded = self._ensure_loaded()
        if loaded is None:
            return "", 0.0
        engine, np = loaded
        result = engine(np.asarray(image.convert("RGB")))
        texts = getattr(result, "txts", None) or ()
        scores = getattr(result, "scores", None) or ()
        if not texts:
            return "", 0.0
        mean_conf = sum(float(s) for s in scores) / len(scores) if len(scores) == len(texts) else 0.0
        return "\n".join(str(t) for t in texts), mean_conf
