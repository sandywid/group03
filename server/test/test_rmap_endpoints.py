# test/test_rmap_endpoints.py
import io
import json
import pytest

pytestmark = pytest.mark.usefixtures("require_db")

class FakeRMAP:
    """Minimal fake som vi kan styra i varje test via attributes/lambdas."""
    def __init__(self):
        self._m1 = None
        self._m2 = None
        self.nonces = {}  # {identity: (nonceClient, nonceServer)}

    def handle_message1(self, payload):
        assert isinstance(payload, dict) and "payload" in payload
        if callable(self._m1):
            return self._m1(payload)
        return {"payload": "BASE64_FROM_FAKE"}

    def handle_message2(self, payload):
        assert isinstance(payload, dict) and "payload" in payload
        if callable(self._m2):
            return self._m2(payload)
        # default: returnera nonces (ints)
        return {"nonce_client": 1, "nonce_server": 2}


# --------------------------
# /api/rmap-initiate
# --------------------------

def test_rmap_initiate_happy_path(client, monkeypatch):
    from server import rmap as real_rmap
    fake = FakeRMAP()
    fake._m1 = lambda p: {"payload": "cGdwX3BheWxvYWRfZmw="}  # nån base64-sträng
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-initiate", json={"payload": "BASE64_IN"})
    assert r.status_code == 200
    js = r.get_json()
    assert js == {"payload": "cGdwX3BheWxvYWRfZmw="}

    # återställ (bra hygien om andra tester litar på server.rmap)
    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_initiate_missing_payload(client, monkeypatch):
    from server import rmap as real_rmap
    fake = FakeRMAP()
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-initiate", json={})
    assert r.status_code == 400
    assert "Missing 'payload'" in r.get_data(as_text=True)

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_initiate_invalid_message(client, monkeypatch):
    from server import rmap as real_rmap
    fake = FakeRMAP()
    fake._m1 = lambda p: (_ for _ in ()).throw(RuntimeError("bad m1"))  # raise
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-initiate", json={"payload": "AAA"})
    assert r.status_code == 400
    assert "Invalid Message1" in r.get_data(as_text=True)

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


# --------------------------
# /api/rmap-get-link
# --------------------------

def test_rmap_get_link_from_dict_nonces(client, monkeypatch):
    """FakeRMAP returnerar nonces som ints -> servern bygger 32-hex länk."""
    from server import rmap as real_rmap
    fake = FakeRMAP()
    fake._m2 = lambda p: {"nonce_client": 1, "nonce_server": 2}
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={"payload": "BASE64"})
    assert r.status_code == 200
    js = r.get_json()
    # 1 => 16 hex nollfyllda, 2 => samma; sammanfogat:
    assert js["result"] == "00000000000000010000000000000002"

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_get_link_from_result_string(client, monkeypatch):
    """FakeRMAP returnerar redan en 32-hex 'result' -> servern ska returnera den."""
    from server import rmap as real_rmap
    fake = FakeRMAP()
    link = "0123456789abcdef0123456789abcdef"
    fake._m2 = lambda p: {"result": link}
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={"payload": "BASE64"})
    assert r.status_code == 200
    assert r.get_json()["result"] == link

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_get_link_from_string_payload(client, monkeypatch):
    """FakeRMAP returnerar en str (t.ex. redan-hex) -> servern hanterar den."""
    from server import rmap as real_rmap
    fake = FakeRMAP()
    link = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    fake._m2 = lambda p: link  # direkt str
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={"payload": "BASE64"})
    assert r.status_code == 200
    assert r.get_json()["result"] == link

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_get_link_identity_lookup_path_is_ok(client, monkeypatch, tmp_path):
    """
    Sätter rmap.nonces så att _identity_from_ns kan hitta identity.
    Vi låter handle_message2 returnera nonces där ns matchar.
    Testet verifierar bara att svaret är 200 och har korrekt result-länk.
    (Vi undviker att asserta på DB/filinnehåll för att hålla det robust.)
    """
    from server import rmap as real_rmap
    fake = FakeRMAP()
    fake.nonces = {"alice@example.com": (0x111, 0x222)}  # ns = 0x222
    fake._m2 = lambda p: {"nonceClient": 0x111, "nonceServer": 0x222}  # camelCase funkar också
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={"payload": "BASE64"})
    assert r.status_code == 200
    assert r.get_json()["result"] == f"{0x111:016x}{0x222:016x}"

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_get_link_missing_payload(client, monkeypatch):
    from server import rmap as real_rmap
    fake = FakeRMAP()
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={})
    assert r.status_code == 400
    assert "Missing 'payload'" in r.get_data(as_text=True)

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)


def test_rmap_get_link_invalid_message(client, monkeypatch):
    from server import rmap as real_rmap
    fake = FakeRMAP()
    fake._m2 = lambda p: (_ for _ in ()).throw(ValueError("bad m2"))
    monkeypatch.setattr("server.rmap", fake, raising=True)

    r = client.post("/api/rmap-get-link", json={"payload": "BASE64"})
    assert r.status_code == 400
    assert "Invalid Message2" in r.get_data(as_text=True)

    monkeypatch.setattr("server.rmap", real_rmap, raising=True)

