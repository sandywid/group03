# test/test_security_authorization.py
import io
import pytest
pytestmark = pytest.mark.usefixtures("require_db")

import random, string, io, pytest
from server import app

def _rand(n=6): return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

import io
import pytest

# Använd rätt fixture-namn för din setup (require_db istället för db_available)
@pytest.fixture
def token_pair(client, require_db):
    """Skapa två separata användare och returnera deras tokens."""
    users = []
    for i in range(2):
        login = f"user{i}"
        email = f"{login}@example.test"
        password = "Passw0rd!"
        r = client.post("/api/create-user", json={"login": login, "email": email, "password": password})
        assert r.status_code in (200, 201), r.get_data(as_text=True)
        login_r = client.post("/api/login", json={"email": email, "password": password})
        js = login_r.get_json()
        assert "token" in js, js
        users.append(js["token"])
    return tuple(users)


@pytest.fixture
def doc_user1(client, token_pair):
    """Skapa ett dokument som tillhör den första användaren."""
    token1, _ = token_pair
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf, "private.pdf"), "name": "private.pdf"}
    r = client.post(
        "/api/upload-document",
        headers={"Authorization": f"Bearer {token1}"},
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()["id"]


def test_owner_isolation_for_get_and_delete(client, token_pair, doc_user1):
    """Verifiera att användare 2 inte kan läsa eller ta bort användare 1:s dokument."""
    _, token2 = token_pair

    # Försök GET
    r = client.get(f"/api/get-document/{doc_user1}", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code in (403, 404), f"Unauthorized read should be forbidden: {r.status_code}"

    # Försök DELETE
    r = client.delete(f"/api/delete-document/{doc_user1}", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code in (403, 404), f"Unauthorized delete should be forbidden: {r.status_code}"
