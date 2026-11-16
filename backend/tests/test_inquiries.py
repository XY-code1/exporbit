import pytest

from tests.conftest import requires_db

pytestmark = requires_db


def inquiry_payload(subject="ANC earbuds inquiry"):
    return {"subject": subject, "raw_text": "We need 1,000 ANC earbuds for Germany.", "source_type": "TEXT", "customer_name": "Nordlicht GmbH"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_create_list_and_get_persisted_inquiry(client):
    created = client.post("/api/v1/inquiries", json=inquiry_payload())
    assert created.status_code == 201
    item = created.json()
    assert item["customer_name"] == "Nordlicht GmbH"
    assert item["revision"] == 1
    listed = client.get("/api/v1/inquiries").json()["items"]
    assert [row["id"] for row in listed] == [item["id"]]
    detail = client.get(f'/api/v1/inquiries/{item["id"]}')
    assert detail.status_code == 200
    assert detail.json()["raw_text"] == inquiry_payload()["raw_text"]


def test_invalid_input_has_structured_error(client):
    response = client.post("/api/v1/inquiries", json={"subject": "", "raw_text": "short", "source_type": "TEXT"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_not_found_has_structured_error(client):
    response = client.get("/api/v1/inquiries/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INQUIRY_NOT_FOUND"


def test_optimistic_concurrency_conflict(client):
    item = client.post("/api/v1/inquiries", json=inquiry_payload()).json()
    first = client.patch(f'/api/v1/inquiries/{item["id"]}', headers={"If-Match": "1"}, json={"subject": "Updated once"})
    assert first.status_code == 200
    assert first.json()["revision"] == 2
    stale = client.patch(f'/api/v1/inquiries/{item["id"]}', headers={"If-Match": "1"}, json={"subject": "Stale write"})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
    assert client.get(f'/api/v1/inquiries/{item["id"]}').json()["subject"] == "Updated once"

