# test/test_delete_robustness.py
import pytest
import io
import uuid

@pytest.mark.parametrize("bad_id", [
    "", "null", "-1", "0", "9999999", "abc", "👾", "%00"
])
def test_delete_with_malformed_or_weird_ids_returns_no_5xx(client, auth_headers, bad_id):
    """
    DELETE /api/delete-document/{id} ska aldrig orsaka 5xx.
    Tillåtna svar: 200, 400, 401, 403, 404 — men aldrig 5xx.
    """
    r = client.delete(f"/api/delete-document/{bad_id}", headers=auth_headers)
    assert r.status_code < 500, f"DELETE gav serverfel för bad_id={bad_id}: {r.status_code} {r.get_data(as_text=True)}"
    assert r.status_code in (200, 400, 401, 403, 404, 405), f"Oväntad statuskod: {r.status_code}"

def test_delete_nonexistent_document_is_handled_gracefully(client, auth_headers):
    # Skapa en uppenbart icke-existerande men rimlig id (UUID-liknande string)
    fake_id = str(uuid.uuid4())
    r = client.delete(f"/api/delete-document/{fake_id}", headers=auth_headers)
    assert r.status_code < 500
    assert r.status_code in (404, 400, 401, 403), f"Förväntade 404/4xx för icke-existerande id, fick {r.status_code}"

def test_delete_after_upload_then_double_delete(client, auth_headers):
    """
    Skapa ett dokument, radera det, försök radera igen — andra delete ska ge 404 eller liknande.
    """
    pdf = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
    data = {"file": (pdf, "todel.pdf"), "name": "todel.pdf"}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    assert r.status_code in (200, 201, 202), r.get_data(as_text=True)
    doc = r.get_json() or {}
    doc_id = doc.get("id")
    assert doc_id is not None, "Upload gav ingen id"

    r1 = client.delete(f"/api/delete-document/{doc_id}", headers=auth_headers)
    assert r1.status_code < 500
    assert r1.status_code in (200, 204, 404, 403)

    r2 = client.delete(f"/api/delete-document/{doc_id}", headers=auth_headers)
    assert r2.status_code < 500
    assert r2.status_code in (404, 400, 401, 403)

