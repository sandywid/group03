# tests/test_auth.py
import io

def test_upload_requires_auth(client, tiny_valid_pdf_bytes):
    data = {"file": (tiny_valid_pdf_bytes, "dummy.pdf")}
    r = client.post("/api/upload-document", data=data, content_type="multipart/form-data")
    assert r.status_code in (401, 403)

def test_upload_with_auth_works(client, auth_headers, tiny_valid_pdf_bytes):
    data = {"file": (tiny_valid_pdf_bytes, "dummy.pdf")}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    assert r.status_code in (200, 201)
    js = r.get_json()
    assert isinstance(js, dict)
    assert any(k in js for k in ("id", "document_id"))

