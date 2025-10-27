# tests/test_idempotency_and_duplicates.py
def test_duplicate_upload_behavior(client, auth_headers, tiny_valid_pdf_bytes):
    data = {"file": (tiny_valid_pdf_bytes, "same_name.pdf")}
    r1 = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    r2 = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")

    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201, 409)  # 409 om ni markerar duplicat; annars ok

    # Om ni returnerar id:er – kontrollera om idempotency stöds eller ej
    j1, j2 = r1.get_json(), r2.get_json()
    id1 = j1.get("document_id") or j1.get("id")
    id2 = j2.get("document_id") or j2.get("id")
    # Acceptera båda varianter: samma ID eller nytt ID
    assert id1 is not None and id2 is not None

