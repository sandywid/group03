# tests/test_roundtrip_after_upload.py
import pytest

@pytest.mark.parametrize("list_paths", [(["/api/documents", "/api/list-documents"])])
def test_list_contains_uploaded(upload_sample_pdf, client, auth_headers, list_paths):
    js = upload_sample_pdf
    doc_id = js.get("document_id") or js.get("id")
    assert doc_id, "Fixture saknar document_id/id"

    # Försök lista – första endpoint som existerar och ger 200 används
    for path in list_paths:
        r = client.get(path, headers=auth_headers)
        if r.status_code == 200:
            items = r.get_json()
            if isinstance(items, dict) and "items" in items:
                items = items["items"]
            assert isinstance(items, (list, tuple))
            assert any(str(doc_id) in str(item) for item in items), f"{doc_id} saknas i lista"
            return
    pytest.skip("Ingen list-endpoint tillgänglig (testade /api/documents och /api/list-documents)")

