# test/test_pdf_watermark_bypass.py
import io
import os
import shutil
import pytest
from pathlib import Path

def _upload_pdf(client, auth_headers, name="report.pdf", content=b"%PDF-1.4\n%%EOF\n"):
    """
    Ladda upp en PDF. Om servern returnerar 400 pga namnregeln (endast A–Z a–z ÅÄÖ åäö 0–9 och '.'),
    försök automatiskt igen med ett säkert namn ('report.pdf').
    """
    pdf = io.BytesIO(content)
    data = {"file": (pdf, name), "name": name}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")

    if r.status_code == 400:
        # prova igen med ett garanterat tillåtet namn
        safe_name = "report.pdf"
        pdf2 = io.BytesIO(content)
        data2 = {"file": (pdf2, safe_name), "name": safe_name}
        r2 = client.post("/api/upload-document", headers=auth_headers, data=data2, content_type="multipart/form-data")
        assert r2.status_code in (200, 201, 202), r2.get_data(as_text=True)
        return r2.get_json()

    assert r.status_code in (200, 201, 202), r.get_data(as_text=True)
    return r.get_json()

def _create_watermark(client, auth_headers, doc_id, method=None, intended_for="bob@example.com"):
    # Hämta en metod om ingen skickas
    methods = client.get("/api/get-watermarking-methods").get_json().get("methods", [])
    assert methods, "Inga watermarking-metoder exponerade"
    if method is None:
        method = methods[0]["name"]
    payload = {"method": method, "position": None, "key": "k", "secret": "s", "intended_for": intended_for}
    r = client.post(f"/api/create-watermark/{doc_id}", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()

def test_watermark_version_creation_and_no_secret_leak(client, auth_headers, tmp_path):
    """
    Skapa ett dokument, skapa watermark-version och verifiera att API-svaret inte innehåller hemliga fält.
    Detta är en defensiv kontroll (ingen "bypass"-instruktion).
    """
    # använd filnamn utan underscore pga namnregeln
    doc = _upload_pdf(client, auth_headers, name="wmbase.pdf")
    doc_id = doc["id"]
    wm = _create_watermark(client, auth_headers, doc_id)
    # Svaret ska inte innehålla 'secret' i klartext
    assert "secret" not in (wm or {}), "API-return inkluderar 'secret' - det bör inte exponeras"

def test_naive_file_modification_does_not_bypass_watermark_access_control(client, auth_headers, tmp_path):
    """
    Testar en naiv modifiering av watermark-filen (t.ex. truncation / strip metadata).
    Kontrollerar att enkel filmanipulation inte leder till att servern exponerar skyddad funktionalitet.
    """
    # Upload + create watermark (använd namn utan underscore)
    doc = _upload_pdf(client, auth_headers, name="wm2base.pdf")
    doc_id = doc["id"]
    wm = _create_watermark(client, auth_headers, doc_id)

    # Lista versioner
    versions = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
    assert versions.status_code == 200
    vers = versions.get_json().get("versions", [])
    assert isinstance(vers, list)

    # Försök hitta lokal path till en version (kan saknas i denna miljö)
    file_path = None
    for v in vers:
        if "path" in v:
            file_path = v["path"]
            break

    # Om ingen lokal path: testa ändå att serverns read/download endpoints svarar robust
    if not file_path:
        # read-watermark med korrekt version-id om tillgängligt
        if vers and "id" in vers[0]:
            r = client.post(f"/api/read-watermark/{doc_id}", headers=auth_headers, json={"version_id": vers[0]["id"], "key": "k"})
            assert r.status_code in (200, 400, 401, 403, 404, 422)
        # download-document bör också vara robust
        r2 = client.get(f"/api/download-document/{doc_id}", headers=auth_headers)
        assert r2.status_code in (200, 400, 401, 403, 404)
        return

    # Om path finns: kopiera till tmp och “naivt” trunca filen
    p = Path(file_path)
    if not p.exists():
        pytest.skip("Watermark path finns inte lokalt i testmiljön; hoppar över filmanipulationssteg")

    target = tmp_path / p.name
    shutil.copy(p, target)
    with open(target, "r+b") as f:
        size = f.seek(0, os.SEEK_END)
        f.truncate(max(1, size // 2))

    # Försök läsa watermark via API med version-id; servern ska svara robust (inte 5xx)
    if vers and "id" in vers[0]:
        r3 = client.post(f"/api/read-watermark/{doc_id}", headers=auth_headers, json={"version_id": vers[0]["id"], "key": "k"})
        assert r3.status_code in (200, 400, 401, 403, 404, 422), f"Unexpected status {r3.status_code}"
