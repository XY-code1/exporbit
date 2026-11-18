from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.application.inquiry_file_import_service import IncomingFile, InquiryFileImportService
from app.domains.inquiry.file_models import InquiryFile
from app.domains.inquiry.models import Inquiry
from app.providers.documents.contracts import MAX_FILE_BYTES

CORPUS = Path(__file__).resolve().parents[1] / "data" / "poc03_corpus"


def load(name: str) -> bytes:
    return (CORPUS / name).read_bytes()


class FakeSession:
    def __init__(self, *, fail_commit: bool = False, fail_flush: bool = False):
        self.records = []
        self.committed = False
        self.rolled_back = False
        self.fail_commit = fail_commit
        self.fail_flush = fail_flush
        self.flushed_inquiry_ids = set()
        self.flush_count = 0
        self.expunged_records = []

    def add(self, record):
        if isinstance(record, InquiryFile) and record.inquiry_id is not None:
            assert record.inquiry_id in self.flushed_inquiry_ids, "Parent inquiry must be flushed before its file"
        self.records.append(record)

    def flush(self):
        self.flush_count += 1
        if self.fail_flush:
            raise RuntimeError("synthetic flush failure")
        self.flushed_inquiry_ids.update(
            record.id for record in self.records if isinstance(record, Inquiry)
        )

    def refresh(self, record, attribute_names=None):
        assert attribute_names == ["created_at"]
        record.created_at = datetime.now(timezone.utc)

    def expunge(self, record):
        self.expunged_records.append(record)

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("synthetic commit failure")
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def incoming(filename: str, data: bytes, content_type: str = "application/pdf") -> IncomingFile:
    return IncomingFile(filename, content_type, len(data), data)


def test_import_batch_persists_success_and_file_level_parse_failure(tmp_path):
    session = FakeSession()
    unrelated = object()
    session.records.append(unrelated)
    good_bytes = load("pdf_text_en_2p.pdf")
    bad_bytes = load("pdf_corrupted.pdf")

    items = InquiryFileImportService(session, tmp_path).import_files(
        [
            incoming("../../buyer-rfq.pdf", good_bytes),
            incoming("broken.pdf", bad_bytes),
        ]
    )

    assert session.committed is True
    assert len(session.expunged_records) == 3
    assert unrelated not in session.expunged_records
    assert all(isinstance(record, (Inquiry, InquiryFile)) for record in session.expunged_records)
    assert [item.parse_status for item in items] == ["SUCCESS", "FAILED"]
    assert items[0].original_name == "buyer-rfq.pdf"
    assert items[0].source_type == "PDF"
    assert items[0].inquiry_id is not None
    assert items[0].created_at is not None
    assert "QUANTITY 500 UNITS" in items[0].preview_text
    assert items[1].inquiry_id is None
    assert items[1].error_code == "CORRUPTED"

    inquiries = [record for record in session.records if isinstance(record, Inquiry)]
    file_records = [record for record in session.records if isinstance(record, InquiryFile)]
    assert len(inquiries) == 1
    assert inquiries[0].raw_text.startswith("Nordlicht GmbH inquiry")
    assert len(file_records) == 2
    for record, original in zip(file_records, (good_bytes, bad_bytes), strict=True):
        assert record.sha256 is not None
        assert record.storage_key is not None
        assert (tmp_path / record.storage_key).read_bytes() == original
    assert file_records[0].parsed_document["pages"][0]["source"] == "text_layer"
    assert file_records[1].parsed_document is None


def test_import_eml_creates_eml_inquiry_and_keeps_attachment_provenance(tmp_path):
    session = FakeSession()
    eml = load("eml_plain_with_pdf_attachment.eml")

    item = InquiryFileImportService(session, tmp_path).import_files(
        [incoming("buyer-email.eml", eml, "message/rfc822")]
    )[0]

    assert item.parse_status == "SUCCESS"
    assert item.source_type == "EML"
    assert "EML-BODY-771" in item.preview_text
    assert item.attachments[0]["filename"] == "quotation.pdf"
    assert item.attachments[0]["parsed"] is True
    inquiry = next(record for record in session.records if isinstance(record, Inquiry))
    assert "PAGE-TWO-7Q4" in inquiry.raw_text


def test_oversize_file_is_reported_without_writing_blob(tmp_path):
    session = FakeSession()
    item = InquiryFileImportService(session, tmp_path).import_files(
        [IncomingFile("huge.pdf", "application/pdf", MAX_FILE_BYTES + 1, None)]
    )[0]

    assert item.parse_status == "FAILED"
    assert item.error_code == "FILE_TOO_LARGE"
    assert item.byte_size == MAX_FILE_BYTES + 1
    assert item.sha256 is None
    assert list(tmp_path.iterdir()) == []
    assert session.committed is True


def test_commit_failure_rolls_back_and_removes_newly_written_upload(tmp_path):
    session = FakeSession(fail_commit=True)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        InquiryFileImportService(session, tmp_path).import_files(
            [incoming("buyer.pdf", load("pdf_text_en_2p.pdf"))]
        )

    assert session.rolled_back is True
    assert list(tmp_path.iterdir()) == []


def test_parent_flush_failure_is_not_misclassified_as_parse_failure_and_cleans_upload(tmp_path):
    session = FakeSession(fail_flush=True)
    with pytest.raises(RuntimeError, match="synthetic flush failure"):
        InquiryFileImportService(session, tmp_path).import_files(
            [incoming("buyer.pdf", load("pdf_text_en_2p.pdf"))]
        )
    assert session.rolled_back is True
    assert session.committed is False
    assert not any(isinstance(record, InquiryFile) for record in session.records)
    assert list(tmp_path.iterdir()) == []
