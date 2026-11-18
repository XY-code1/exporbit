from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import settings
from app.domains.inquiry.file_models import InquiryFile
from app.domains.inquiry.models import Inquiry
from tests.conftest import TestingSession, requires_db

pytestmark = requires_db
CORPUS = Path(__file__).resolve().parents[1] / "data" / "poc03_corpus"


def test_import_files_creates_inquiries_and_keeps_individual_failures(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "file_storage_path", tmp_path)
    valid_pdf = (CORPUS / "pdf_text_en_2p.pdf").read_bytes()
    broken_pdf = (CORPUS / "pdf_corrupted.pdf").read_bytes()

    response = client.post(
        "/api/v1/inquiries/import",
        files=[
            ("files", ("buyer-rfq.pdf", valid_pdf, "application/pdf")),
            ("files", ("broken.pdf", broken_pdf, "application/pdf")),
        ],
    )

    assert response.status_code == 201
    items = response.json()["items"]
    assert [item["parse_status"] for item in items] == ["SUCCESS", "FAILED"]
    assert items[0]["source_type"] == "PDF"
    assert items[0]["inquiry_id"]
    assert items[0]["sha256"]
    assert "QUANTITY 500 UNITS" in items[0]["preview_text"]
    assert items[1]["inquiry_id"] is None
    assert items[1]["error_code"] == "CORRUPTED"

    inquiry_id = items[0]["inquiry_id"]
    detail = client.get(f"/api/v1/inquiries/{inquiry_id}")
    assert detail.status_code == 200
    assert "QUANTITY 500 UNITS" in detail.json()["raw_text"]

    persisted = client.get(f"/api/v1/inquiries/{inquiry_id}/files")
    assert persisted.status_code == 200
    assert persisted.json()["items"][0]["preview_text"] == items[0]["preview_text"]

    with TestingSession() as session:
        file_record = session.get(InquiryFile, UUID(items[0]["file_id"]))
        assert file_record is not None
        assert file_record.parse_status == "SUCCESS"
        assert file_record.storage_key is not None
        assert (tmp_path / file_record.storage_key).read_bytes() == valid_pdf
        parent = session.get(Inquiry, file_record.inquiry_id)
        assert parent is not None
        assert str(parent.id) == inquiry_id
        assert "QUANTITY 500 UNITS" in parent.raw_text
        failed_record = session.get(InquiryFile, UUID(items[1]["file_id"]))
        assert failed_record is not None
        assert failed_record.inquiry_id is None
        assert failed_record.parse_status == "FAILED"
        assert failed_record.error_code == "CORRUPTED"
