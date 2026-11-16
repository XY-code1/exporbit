"""Document parsing providers (POC-03).

Local-only stack: pdfplumber (MIT) for PDF text, pypdf (BSD-3) for encryption
detection, Pillow (MIT-CMU) for images, RapidOCR/onnxruntime (Apache-2.0) for
offline OCR, stdlib email for EML. Kept behind a provider boundary so a hosted
parser could replace it without touching domain code.
"""
from app.providers.documents.contracts import (  # noqa: F401
    MAX_FILE_BYTES,
    MAX_PDF_PAGES,
    AttachmentInfo,
    DocumentParser,
    PageText,
    ParsedDocument,
    ParseError,
    ParseErrorCode,
)
from app.providers.documents.dispatcher import detect_format, parse_document  # noqa: F401
from app.providers.documents.ocr import OcrEngine, RapidOcrEngine  # noqa: F401
