# Added this for the fuzzing specialization task /Adna
# server/test/test_regressions.py
import io
import pytest

from server import app  # noqa: F401

pytestmark = [pytest.mark.usefixtures("require_db")]

# LOGIN / CREATE-USER

def test_login_rejects_list_body(client):
    # Previously crashed when body was a list
    resp = client.post("/api/login", json=[{"email": "oops"}])
    assert resp.status_code in (400, 401)

def test_login_invalid_json_returns_400(client):
    # Malformed JSON should not 500
    resp = client.post("/api/login", data="not-json", content_type="application/json")
    assert resp.status_code in (400, 401)

def test_create_user_invalid_json_returns_400(client):
    resp = client.post("/api/create-user", data="not-json", content_type="application/json")
    assert resp.status_code in (400, 422)

# READ WATERMARK

def test_read_watermark_only_key_required(client, auth_headers):
    resp = client.post("/api/read-watermark/1", json={"key": "testkey"}, headers=auth_headers)
    # Must not 5xx even if doc 1 doesn't exist in this DB snapshot
    assert resp.status_code < 500

def test_read_watermark_missing_key_returns_400(client, auth_headers):
    resp = client.post("/api/read-watermark/1", json={}, headers=auth_headers)
    assert resp.status_code == 400

# UPLOAD DOCUMENT

def test_upload_rejects_non_pdf(client, auth_headers):
    # Bytes that are not a PDF but with a .pdf filename
    data = {"file": (io.BytesIO(b"NOT_A_PDF"), "fake.pdf"), "name": "fake.pdf"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    # Expect a client error (not a server crash)
    assert r.status_code in (400, 415), r.get_data(as_text=True)

def test_upload_rejects_bad_name(client, auth_headers, tiny_valid_pdf_bytes):
    # Attempt path traversal in 'name'
    data = {"file": (io.BytesIO(tiny_valid_pdf_bytes), "report.pdf"), "name": "../etc/passwd"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (400, 422), r.get_data(as_text=True)

# PUBLIC / LINKED VERSIONS

def test_get_version_not_found_returns_404(client):
    r = client.get("/api/get-version/not-a-real-link-xyz")
    assert r.status_code in (404, 400), r.get_data(as_text=True)

# AUTH GUARD (NEGATIVE)

def test_private_requires_auth_list_documents(client):
    # Hitting a private endpoint without auth should be blocked
    r = client.get("/api/list-documents")
    assert r.status_code in (401, 403)
