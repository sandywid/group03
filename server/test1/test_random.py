# server/test/test_random.py
import io
import random, string

def _signup_and_login(client):
    suf = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    email = f"{suf}@example.test"
    password = "Pw123456!"
    client.post("/api/create-user", json={"login": suf, "email": email, "password": password})
    js = client.post("/api/login", json={"email": email, "password": password}).get_json() or {}
    assert "token" in js, f"login failed: {js}"   # be defensive
    return {"Authorization": f"Bearer {js['token']}"}

def test_missing_file(client, require_db):
    headers = _signup_and_login(client)
    r = client.post("/api/upload-document", headers=headers, data={"name": "no_file.pdf"})
    assert r.status_code in (400, 422)

def test_wrong_mimetype(client, require_db):
    headers = _signup_and_login(client)
    r = client.post(
        "/api/upload-document",
        headers=headers,
        data={"name": "fake.pdf", "file": (io.BytesIO(b"NOT_A_REAL_PDF"), "fake.pdf")},
        content_type="multipart/form-data",
    )
    assert r.status_code in (400, 415)
