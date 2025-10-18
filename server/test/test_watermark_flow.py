# Added this for the fuzzing specialization task as a verification /Adna
import io
import pytest
from server import app

client = app.test_client()

@pytest.mark.timeout(30)
def test_full_watermark_upload_flow(tmp_path):
    """Integration-like test: upload → create watermark → read watermark."""
    # Create a fake PDF file
    fake_pdf = io.BytesIO(b"%PDF-1.4\n%Fake PDF\n%%EOF")
    fake_pdf.name = "sample.pdf"

    # Register + login
    email = "fuzz_user@example.test"
    password = "fuzzpass"
    client.post("/api/create-user", json={"email": email, "password": password})
    resp = client.post("/api/login", json={"email": email, "password": password})
    token = None
    try:
        j = resp.get_json(silent=True)
        token = j.get("token") or j.get("access_token")
        if token and not token.startswith("Bearer "):
            token = f"Bearer {token}"
    except Exception:
        token = None

    headers = {"Authorization": token} if token else {}

    # Upload fake document
    resp_up = client.post("/api/upload-document", headers=headers, data={"file": (fake_pdf, fake_pdf.name)})
    assert resp_up.status_code < 500, f"Upload failed: {resp_up.status_code}"
    doc = resp_up.get_json(silent=True) or {}
    document_id = doc.get("id") or doc.get("documentid") or 1

    # Create watermark
    payload = {
        "key": "fuzzkey123",
        "secret": "fuzzsecret",
        "method": "test-method",
        "intended_for": "fuzz-test",
        "position": ""
    }
    resp_wm = client.post(f"/api/create-watermark/{document_id}", json=payload, headers=headers)
    assert resp_wm.status_code < 500, f"Watermark creation crashed: {resp_wm.status_code}"

    # Read watermark back
    resp_rd = client.post("/api/read-watermark", json={"key": "fuzzkey123"}, headers=headers)
    assert resp_rd.status_code < 500, f"Read watermark crashed: {resp_rd.status_code}"
