from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.inquiry.file_models import InquiryFile
from app.domains.inquiry.models import Inquiry
from app.infrastructure.database import get_session
from app.main import app

CORPUS = Path(__file__).resolve().parents[1] / "data" / "poc03_corpus"


class FakeSession:
    def __init__(self):
        self.records = []
        self.committed = False

    def add(self, record):
        self.records.append(record)

    def flush(self):
        pass

    def refresh(self, record, attribute_names=None):
        assert attribute_names == ["created_at"]
        record.created_at = datetime.now(timezone.utc)

    def expunge(self, record):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_multipart_route_returns_success_and_failure_per_file(monkeypatch, tmp_path):
    session = FakeSession()
    monkeypatch.setattr(settings, "file_storage_path", tmp_path)

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/inquiries/import",
                files=[
                    ("files", ("buyer-rfq.pdf", (CORPUS / "pdf_text_en_2p.pdf").read_bytes(), "application/pdf")),
                    ("files", ("broken.pdf", (CORPUS / "pdf_corrupted.pdf").read_bytes(), "application/pdf")),
                ],
            )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    items = response.json()["items"]
    assert [item["parse_status"] for item in items] == ["SUCCESS", "FAILED"]
    assert items[0]["source_type"] == "PDF"
    assert items[0]["created_at"] is not None
    assert "QUANTITY 500 UNITS" in items[0]["preview_text"]
    assert items[1]["error_code"] == "CORRUPTED"
    assert session.committed is True
    assert sum(isinstance(record, Inquiry) for record in session.records) == 1
    file_records = [record for record in session.records if isinstance(record, InquiryFile)]
    assert len(file_records) == 2
    assert all((tmp_path / record.storage_key).is_file() for record in file_records)
