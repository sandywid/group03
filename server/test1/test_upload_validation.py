# tests/test_upload_validation.py
import io

def test_upload_without_file_param(client, auth_headers):
    r = client.post("/api/upload-document", headers=auth_headers, data={}, content_type="multipart/form-data")
    assert r.status_code in (400, 422)

def test_upload_rejects_non_multipart(client, auth_headers):
    r = client.post("/api/upload-document", headers=auth_headers, data=b"not-multipart")
    # Borde ej acceptera raw body
    assert r.status_code in (400, 415, 422)

def test_upload_rejects_wrong_extension(client, auth_headers):
    data = {"file": (io.BytesIO(b"hello"), "note.txt")}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    # Förvänta valideringsfel om endast PDF tillåts
    assert r.status_code in (400, 415, 422)

