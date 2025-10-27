# tests/test_bad_tokens.py
import io
import pytest

@pytest.mark.parametrize("hdrs", [
    {"Authorization": "Bearer bad.token"},
    {"Authorization": "Bearer"},
    {"Authorization": "Token abc"},
    {}
])
def test_upload_rejects_bad_tokens(client, tiny_valid_pdf_bytes, hdrs):
    data = {"file": (tiny_valid_pdf_bytes, "dummy.pdf")}
    r = client.post("/api/upload-document", headers=hdrs, data=data, content_type="multipart/form-data")
    assert r.status_code in (401, 403)

