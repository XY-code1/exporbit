"""Document parsing tests: text layers, provenance, EML policy, controlled failures.

Fixtures are the synthetic corpus in backend/data/poc03_corpus (no real data).
OCR is stubbed here so these tests run without model files.
"""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from app.providers.documents import ParseError, ParseErrorCode, parse_document
from app.providers.documents import dispatcher, pdf

CORPUS = Path(__file__).resolve().parents[1] / "data" / "poc03_corpus"


def load(name: str) -> bytes:
    return (CORPUS / name).read_bytes()


class FakeOcr:
    def __init__(self, text: str = "quantity 500 units", confidence: float = 0.95) -> None:
        self.text = text
        self.confidence = confidence
        self.calls = 0

    @property
    def available(self) -> bool:
        return True

    def extract(self, image) -> tuple[str, float]:
        self.calls += 1
        return self.text, self.confidence


def test_digital_pdf_text_layer_and_page_provenance() -> None:
    doc = parse_document("pdf_text_en_2p.pdf", load("pdf_text_en_2p.pdf"), ocr=FakeOcr())
    assert doc.format == "pdf"
    assert len(doc.pages) == 2
    assert [page.page_number for page in doc.pages] == [1, 2]
    assert {page.source for page in doc.pages} == {"text_layer"}
    assert "QUANTITY 500 UNITS" in doc.pages[0].text
    assert "PAGE-TWO-7Q4" in doc.pages[1].text
    assert not doc.used_ocr


def test_chinese_text_layer_preserves_characters() -> None:
    doc = parse_document("pdf_text_cn_1p.pdf", load("pdf_text_cn_1p.pdf"), ocr=FakeOcr())
    assert "3000 条智能手环" in doc.pages[0].text
    assert "CN-TOKEN-3000" in doc.pages[0].text


def test_eml_body_and_attachment_pages_have_provenance() -> None:
    doc = parse_document("eml_plain_with_pdf_attachment.eml", load("eml_plain_with_pdf_attachment.eml"), ocr=FakeOcr())
    assert doc.format == "eml"
    assert len(doc.pages) == 3
    assert doc.pages[0].source == "email_body"
    assert "EML-BODY-771" in doc.pages[0].text
    assert doc.pages[1].source == "attachment:quotation.pdf"
    assert doc.pages[2].source == "attachment:quotation.pdf"
    assert "PAGE-TWO-7Q4" in doc.pages[2].text
    assert [page.page_number for page in doc.pages] == [1, 2, 3]
    attachment = doc.attachments[0]
    assert attachment.filename == "quotation.pdf"
    assert attachment.parsed is True


def test_eml_executable_attachment_is_blocked_not_parsed() -> None:
    doc = parse_document("eml_with_exe_attachment.eml", load("eml_with_exe_attachment.eml"), ocr=FakeOcr())
    assert "EML-EXE-990" in doc.pages[0].text
    attachment = doc.attachments[0]
    assert attachment.filename == "invoice.exe"
    assert attachment.parsed is False
    assert attachment.skip_reason == "executable_blocked"
    assert any("executable_blocked" in warning for warning in doc.warnings)


def test_eml_html_only_body_is_converted_to_text() -> None:
    doc = parse_document("eml_html_only.eml", load("eml_html_only.eml"), ocr=FakeOcr())
    assert len(doc.pages) == 1
    assert doc.pages[0].source == "email_body"
    assert "EML-HTML-882" in doc.pages[0].text
    assert "2000 smart doorbells" in doc.pages[0].text
    assert "<p>" not in doc.pages[0].text


def _eml_with_attachment(filename: str, payload: bytes, maintype="application", subtype="octet-stream") -> bytes:
    message = EmailMessage()
    message["From"] = "buyer@example.com"
    message["To"] = "sales@exporbit.example"
    message["Subject"] = "Inquiry"
    message.set_content("Test body with token ATTACH-TEST-1.")
    message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


def test_eml_unsupported_attachment_type_skipped() -> None:
    doc = parse_document("mail.eml", _eml_with_attachment("archive.zip", b"PK\x03\x04fake"), ocr=FakeOcr())
    assert doc.attachments[0].skip_reason == "unsupported_type"
    assert len(doc.pages) == 1


def test_eml_nested_email_skipped() -> None:
    doc = parse_document("mail.eml", _eml_with_attachment("forwarded.eml", b"From: a@b.c\n\nhello"), ocr=FakeOcr())
    assert doc.attachments[0].skip_reason == "nested_email"


def test_eml_attachment_failure_is_recorded_and_body_survives() -> None:
    doc = parse_document("mail.eml", _eml_with_attachment("broken.pdf", load("pdf_corrupted.pdf")), ocr=FakeOcr())
    assert doc.attachments[0].skip_reason == "parse_failed:CORRUPTED"
    assert len(doc.pages) == 1
    assert "ATTACH-TEST-1" in doc.pages[0].text


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("pdf_corrupted.pdf", ParseErrorCode.CORRUPTED),
        ("pdf_encrypted.pdf", ParseErrorCode.ENCRYPTED),
        ("img_corrupted.jpg", ParseErrorCode.CORRUPTED),
        ("file_unsupported.docx", ParseErrorCode.UNSUPPORTED_FORMAT),
    ],
)
def test_controlled_failures_report_exact_error_code(filename: str, expected: ParseErrorCode) -> None:
    with pytest.raises(ParseError) as caught:
        parse_document(filename, load(filename), ocr=FakeOcr())
    assert caught.value.code is expected


def test_blank_scan_reports_empty_text() -> None:
    with pytest.raises(ParseError) as caught:
        parse_document("pdf_blank_scan.pdf", load("pdf_blank_scan.pdf"), ocr=FakeOcr(text=""))
    assert caught.value.code is ParseErrorCode.EMPTY_TEXT


def test_magic_bytes_detect_pdf_when_extension_unknown() -> None:
    doc = parse_document("attachment.bin", load("pdf_text_en_2p.pdf"), ocr=FakeOcr())
    assert doc.format == "pdf"
    assert len(doc.pages) == 2


def test_empty_file_is_rejected_as_corrupted() -> None:
    with pytest.raises(ParseError) as caught:
        parse_document("empty.pdf", b"", ocr=FakeOcr())
    assert caught.value.code is ParseErrorCode.CORRUPTED


def test_file_size_limit_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatcher, "MAX_FILE_BYTES", 16)
    with pytest.raises(ParseError) as caught:
        parse_document("pdf_text_en_2p.pdf", load("pdf_text_en_2p.pdf"), ocr=FakeOcr())
    assert caught.value.code is ParseErrorCode.FILE_TOO_LARGE


def test_pdf_page_limit_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "MAX_PDF_PAGES", 1)
    with pytest.raises(ParseError) as caught:
        parse_document("pdf_text_en_2p.pdf", load("pdf_text_en_2p.pdf"), ocr=FakeOcr())
    assert caught.value.code is ParseErrorCode.TOO_MANY_PAGES
