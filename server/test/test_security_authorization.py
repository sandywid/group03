# test/test_security_authorization.py
import pytest
pytestmark = pytest.mark.usefixtures("require_db")

import random, string, io, pytest
from server import app

def _rand(n=6): return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


@pytest.fixture
def token_pair(client, db_available):
    def mk():
        suf = _rand()
        email = f"{suf}@ex.amp.le"
        client.post("/api/create-user", json={"login": suf, "email": email, "password": "Pw123456!"})
        r = client.post("/api/login", json={"email": email, "password": "Pw123456!"})
        js = r.get_json() or {}
        assert r.status_code == 200 and "token" in js, f"login failed: {r.status_code} {js}"
        return js["token"]
    return mk(), mk()

@pytest.fixture
def doc_user1(client, token_pair, tiny_valid_pdf_bytes):
    t1, _ = token_pair
    r = client.post("/api/upload-document",
                    headers={"Authorization": f"Bearer {t1}"},
                    data={"file": (io.BytesIO(tiny_valid_pdf_bytes), "a.pdf"), "name": "a.pdf"},
                    content_type="multipart/form-data")
    assert r.status_code == 201
    return r.get_json()["id"]

def test_owner_isolation_for_get_and_delete(client, token_pair, doc_user1):
    t1, t2 = token_pair
    # user2 is NOT allowed to ses user1:s document
    r = client.get(f"/api/get-document/{doc_user1}", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code == 404  # servern hides the existense
    # user2 is not allowed to delete user1:s document
    r = client.delete(f"/api/delete-document/{doc_user1}", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code == 404
