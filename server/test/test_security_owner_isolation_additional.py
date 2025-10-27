# test/test_security_owner_isolation_additional.py
import io
import uuid

def _unique_user(prefix="u"):
    login = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{login}@example.test"
    password = "P@ssw0rd!"
    return login, email, password

def _get_token_from_login(resp):
    js = resp.get_json() or {}
    for key in ("token", "access_token", "accessToken"):
        if key in js:
            return js[key]
    raise AssertionError(f"No token found in login response: {js}")

def test_owner_cannot_access_others_document(client):
    # Skapa user1
    l1, e1, p1 = _unique_user("u1")
    r = client.post("/api/create-user", json={"login": l1, "email": e1, "password": p1})
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    t1 = _get_token_from_login(client.post("/api/login", json={"email": e1, "password": p1}))

    # Skapa user2
    l2, e2, p2 = _unique_user("u2")
    r = client.post("/api/create-user", json={"login": l2, "email": e2, "password": p2})
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    t2 = _get_token_from_login(client.post("/api/login", json={"email": e2, "password": p2}))

    # u1 laddar upp ett dokument
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf, "secret.pdf"), "name": "secret.pdf"}
    r = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {t1}"},
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    doc_id = r.get_json()["id"]

    # u2 ska inte kunna läsa eller radera u1:s dokument
    r = client.get(f"/api/get-document/{doc_id}", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code in (403, 404)
    r = client.delete(f"/api/delete-document/{doc_id}", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code in (403, 404)
