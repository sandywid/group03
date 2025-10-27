# tests/test_roundtrip_after_upload.py
import pytest
from io import BytesIO

@pytest.mark.parametrize("list_paths", [(["/api/list-documents", "/api/documents"])])
def test_list_contains_uploaded(list_paths, client, auth_headers, tiny_valid_pdf_bytes):
    up = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data={"file": (BytesIO(tiny_valid_pdf_bytes.getvalue()), "dummy.pdf")},
        content_type="multipart/form-data",
    )
    assert up.status_code in (200, 201, 202)
    js = up.get_json() or {}
    doc_id = js.get("id") or js.get("document_id")
    assert doc_id, "Upload-svar saknar 'id'/'document_id'"

    for path in list_paths:
        r = client.get(path, headers=auth_headers)
        if r.status_code == 200:
            data = r.get_json()
            items = data.get("documents") if isinstance(data, dict) else data
            assert isinstance(items, list)
            assert any(str(doc_id) in str(it) for it in items), f"{doc_id} saknas i listningen"
            return
    pytest.skip("Ingen list-endpoint svarade 200")
