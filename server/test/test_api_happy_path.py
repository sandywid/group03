# test/test_api_happy_path.py
import io
import re
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("BASE_URL"),
    reason="Körs bara när BASE_URL är satt (kräver extern server/DB)"
)

def test_list_documents_empty(client, auth_headers):
    r = client.get("/api/list-documents", headers=auth_headers)
    assert r.status_code == 200
    assert "documents" in r.get_json()

def test_upload_and_get_document(client, auth_headers, upload_sample_pdf):
    doc = upload_sample_pdf
    # list sould include the new doc
    r = client.get("/api/list-documents", headers=auth_headers)
    docs = r.get_json()["documents"]
    assert any(d["id"] == doc["id"] for d in docs)

    # fetch the uploaded document
    r = client.get(f"/api/get-document/{doc['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("application/pdf")
    # ETag sould be set from HEX(sha256)
    assert r.headers.get("ETag")

def test_create_watermark_and_list_versions(client, auth_headers, upload_sample_pdf):
    doc = upload_sample_pdf
    # fetch avaliable methods to chose a real one
    r = client.get("/api/get-watermarking-methods")
    methods = r.get_json()["methods"]
    assert methods
    method_name = methods[0]["name"]

    payload = {
        "method": method_name,
        "position": None,
        "key": "unit-test-key",
        "secret": "unit-test-secret",
        "intended_for": "alice@example.com"
    }
    r = client.post(f"/api/create-watermark/{doc['id']}", headers=auth_headers, json=payload)
    assert r.status_code == 200 or r.status_code == 201
    wm = r.get_json()
    assert wm["documentid"] == doc["id"]
    assert "link" in wm and isinstance(wm["link"], str)

    # list versions for the document 
    r = client.get(f"/api/list-versions/{doc['id']}", headers=auth_headers)
    versions = r.get_json()["versions"]
    assert any(v["id"] == wm["id"] for v in versions)

    # public download through /api/get-version/<link> (no auth)
    r = client.get(f"/api/get-version/{wm['link']}")
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("application/pdf")

def test_read_watermark_roundtrip(client, auth_headers, upload_sample_pdf):
    # create watermark → read back the secret with only key (according to our implementation)
    doc = upload_sample_pdf
    m = client.get("/api/get-watermarking-methods").get_json()["methods"][0]["name"]

    # create version
    wm = client.post(f"/api/create-watermark/{doc['id']}", headers=auth_headers, json={
        "method": m, "position": None, "key": "k", "secret": "s3cr3t", "intended_for": "bob@example.com"
    }).get_json()

    # read watermark – allows version_id or link according to our code
    r = client.post(f"/api/read-watermark/{doc['id']}", headers=auth_headers, json={
        "version_id": wm["id"], "key": "k"
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("secret") == "s3cr3t"
    assert data.get("method")  # server returns method

def test_delete_document_removes_row(client, auth_headers, upload_sample_pdf):
    did = upload_sample_pdf["id"]
    r = client.delete(f"/api/delete-document/{did}", headers=auth_headers)
    assert r.status_code == 200
   
    r = client.get(f"/api/get-document/{did}", headers=auth_headers)
    assert r.status_code in (404, 410)
