# test/test_api_happy_path.py
import io
import pytest

pytestmark = pytest.mark.usefixtures("require_db")

def test_list_documents_empty(client, auth_headers):
    r = client.get("/api/list-documents", headers=auth_headers)
    assert r.status_code == 200
    js = r.get_json()
    assert isinstance(js, dict)
    assert "documents" in js
    assert isinstance(js["documents"], list)
    # tom lista vid start av test
    assert js["documents"] == []


def test_upload_and_get_document(client, auth_headers):
    # Ladda upp minimal PDF
    pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf_io, "happy.pdf"), "name": "happy.pdf"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    # Förväntar oss 201 CREATED
    assert r.status_code == 201, r.get_data(as_text=True)
    doc = r.get_json()
    assert {"id", "name", "sha256"} <= set(doc.keys())
    doc_id = doc["id"]

    # Efter uppladdning: dokumentet ska synas i listan
    r = client.get("/api/list-documents", headers=auth_headers)
    assert r.status_code == 200
    docs = r.get_json()["documents"]
    assert any(d["id"] == doc_id for d in docs)

    # Hämta själva PDF:en via get-document (returnerar fil/bytes, ej JSON)
    r = client.get(f"/api/get-document/{doc_id}", headers=auth_headers)
    assert r.status_code == 200
    ctype = r.headers.get("Content-Type", "")
    assert ctype.startswith("application/pdf")
    # ETag bör finnas när sha256 lagras
    assert r.headers.get("ETag")


def test_create_watermark_and_list_versions(client, auth_headers):
    # Ladda upp käll-PDF
    pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf_io, "base.pdf"), "name": "base.pdf"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    doc = r.get_json()
    doc_id = doc["id"]

    # Hämta tillgängliga watermarking-metoder
    r = client.get("/api/get-watermarking-methods")
    assert r.status_code == 200
    methods = r.get_json()["methods"]
    assert isinstance(methods, list) and len(methods) > 0
    method_name = methods[0]["name"]

    # Skapa watermark-version (förväntas 201 CREATED)
    payload = {
        "method": method_name,
        "position": None,
        "key": "unit-test-key",
        "secret": "unit-test-secret",
        "intended_for": "alice@example.com",
    }
    r = client.post(f"/api/create-watermark/{doc_id}", headers=auth_headers, json=payload)
    assert r.status_code == 201, r.get_data(as_text=True)
    wm = r.get_json()
    assert wm["documentid"] == doc_id
    assert "link" in wm and isinstance(wm["link"], str)
    version_id = wm["id"]

    # Lista versioner för dokumentet
    r = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
    assert r.status_code == 200
    versions = r.get_json()["versions"]
    assert any(v["id"] == version_id for v in versions)

    # Publik nedladdning via /api/get-version/<link> (ingen auth krävs)
    r = client.get(f"/api/get-version/{wm['link']}")
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("application/pdf")


def test_read_watermark_roundtrip(client, auth_headers):
    # Ladda upp en PDF
    pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf_io, "rw.pdf"), "name": "rw.pdf"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    doc = r.get_json()
    doc_id = doc["id"]

    # Välj en faktisk metod
    m = client.get("/api/get-watermarking-methods").get_json()["methods"][0]["name"]

    # Skapa version (201)
    wm = client.post(
        f"/api/create-watermark/{doc_id}",
        headers=auth_headers,
        json={"method": m, "position": None, "key": "k", "secret": "s3cr3t", "intended_for": "bob@example.com"},
    ).get_json()

    # Läs tillbaka watermark – servern accepterar version_id + key
    r = client.post(
        f"/api/read-watermark/{doc_id}",
        headers=auth_headers,
        json={"version_id": wm["id"], "key": "k"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("secret") == "s3cr3t"
    assert data.get("method")


def test_delete_document_removes_row(client, auth_headers):
    # Ladda upp dokument
    pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf_io, "todelete.pdf"), "name": "todelete.pdf"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    doc = r.get_json()
    doc_id = doc["id"]

    # Radera (200 OK)
    r = client.delete(f"/api/delete-document/{doc_id}", headers=auth_headers)
    assert r.status_code == 200

    # Ska inte gå att hämta längre (404)
    r = client.get(f"/api/get-document/{doc_id}", headers=auth_headers)
    assert r.status_code == 404
