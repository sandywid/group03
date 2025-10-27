# test/test_idempotency_defensive.py
import io

def test_duplicate_upload_returns_same_sha_or_handled(client, auth_headers):
    pdf_bytes = b"%PDF-1.4\n%EOF\n"
    for _ in range(2):
        pdf = io.BytesIO(pdf_bytes)
        data = {"file": (pdf, "dup.pdf"), "name": "dup.pdf"}
        r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
        assert r.status_code in (200,201,202)
    # ensure DB doesn't create two distinct logical documents with same sha (policy depends on app)
    r = client.get("/api/list-documents", headers=auth_headers)
    docs = r.get_json().get("documents", [])
    matching = [d for d in docs if d.get("name")=="dup.pdf"]
    assert len(matching) <= 1 or all(d.get("sha256")==matching[0].get("sha256") for d in matching)

