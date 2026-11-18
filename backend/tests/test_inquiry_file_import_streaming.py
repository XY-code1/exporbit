from io import BytesIO
from types import SimpleNamespace

from app.api import inquiries as inquiries_api
from app.providers.documents.contracts import MAX_FILE_BYTES


class TrackedBytesIO(BytesIO):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.read_sizes = []
        self.rolled_over = False

    def rollover(self):
        self.rolled_over = True

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def upload(filename: str, data: bytes):
    return SimpleNamespace(
        filename=filename,
        content_type="application/pdf",
        file=TrackedBytesIO(data),
    )


def test_import_route_reads_each_upload_only_when_service_requests_it(monkeypatch):
    first_upload = upload("first.pdf", b"first")
    second_upload = upload("second.pdf", b"second")

    class InspectingImportService:
        def __init__(self, session, storage_dir):
            assert session is sentinel_session

        def import_files(self, incoming_files):
            assert iter(incoming_files) is incoming_files
            assert first_upload.file.rolled_over is True
            assert second_upload.file.rolled_over is True
            first = next(incoming_files)
            assert first.data == b"first"
            assert second_upload.file.read_sizes == []
            del first
            second = next(incoming_files)
            assert second.data == b"second"
            assert first_upload.file.read_sizes == [MAX_FILE_BYTES + 1]
            assert second_upload.file.read_sizes == [MAX_FILE_BYTES + 1]
            return []

    sentinel_session = object()
    monkeypatch.setattr(inquiries_api, "InquiryFileImportService", InspectingImportService)

    response = inquiries_api.import_inquiry_files([first_upload, second_upload], sentinel_session)

    assert response.items == []
