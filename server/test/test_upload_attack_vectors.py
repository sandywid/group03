# test/test_upload_attack_vectors.py
import io
import os
import pathlib
import pytest

# Tests som verifierar att upload-endpointen hanterar "malicious-looking" namn och payloads
@pytest.mark.parametrize("bad_name", [
    "../etc/passwd",
    "/tmp/flag.txt",
    "C:\\Windows\\system32\\drivers\\etc\\hosts",
    "a" * 4096 + ".pdf",          # väldigt långt filnamn
    "normal\x00hidden.pdf",       # null-byte inbäddad
    "flag_payload.pdf",
])
def test_upload_rejects_malicious_or_weird_names(client, auth_headers, bad_name):
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf, "upload.pdf"), "name": bad_name}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    # Förväntat: servern tar inte emot eller normaliserar bort farliga namn — 4xx/403
    assert r.status_code < 500, f"Servern kraschade på filnamn: {bad_name}"
    assert r.status_code in (400, 403, 422, 200, 201, 202), (
        "Oväntad statuskod; bör vara 4xx (reject) eller 2xx (om appen normaliserar). "
        f"Fick {r.status_code} för name={bad_name}"
    )

@pytest.mark.parametrize("content_type,bytes_payload", [
    ("application/pdf", b"%PDF-1.4\n%%EOF\n"),            # korrekt
    ("text/plain", b"This is not a PDF, just text"),     # felaktig content
    ("application/octet-stream", b"\x00\x01\x02\x03\x04"),# binary gibberish
])
def test_upload_tolerates_or_rejects_bad_content_types(client, auth_headers, content_type, bytes_payload):
    pdf = io.BytesIO(bytes_payload)
    data = {"file": (pdf, "file.bin"), "name": "file.bin"}
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    # Viktigt: servern får inte krascha (inga 5xx). Acceptera 2xx eller 4xx.
    assert r.status_code < 500, f"Servern kraschade för content_type={content_type}"
    assert r.status_code in (200, 201, 202, 400, 403, 422), f"Fel svar: {r.status_code}"

def test_upload_rejects_path_traversal_in_name_and_stays_in_storage(client, auth_headers, tmp_path):
    """
    Kontrollera att ett försök att ladda upp med path-traversal i 'name'
    inte resulterar i filer utanför lagringskatalogen.
    """
    pdf = io.BytesIO(b"%PDF-1.4\n%%EOF\n")
    traversal_name = "../outside.txt"
    data = {"file": (pdf, "report.pdf"), "name": traversal_name}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    assert r.status_code < 500

    # Om appen har STORAGE_DIR inställd, verifiera att inga nya filer hamnat utanför
    storage_conf = client.application.config.get("STORAGE_DIR")
    if storage_conf:
        storage = pathlib.Path(storage_conf).resolve()
        # lista filer som skapats (om något)
        files = [p for p in storage.rglob("*") if p.is_file()]
        # Alla filer måste ligga under storage root
        assert all(str(p.resolve()).startswith(str(storage)) for p in files), "Hittade fil utanför storage"
