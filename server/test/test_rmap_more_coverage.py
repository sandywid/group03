# test/test_rmap_more_coverage.py
import base64
import json
import pytest

pytestmark = pytest.mark.usefixtures("require_db")


# =========================
# Minimal RMAP-stub
# =========================
class StubRMAP:
    def __init__(self):
        # identity -> (nonce_client, nonce_server)
        self.nonces = {}

    def handle_message1(self, obj):
        # Standard: returnera dict med samma payload som inkom
        return {"payload": obj.get("payload", "")}

    def handle_message2(self, obj):
        # Standard: returnera nonces som ints
        return {"nonce_client": 0xA1B2C3D4E5F60123, "nonce_server": 0x0102030405060708}


@pytest.fixture
def stubbed_rmap(monkeypatch):
    import server
    real = server.rmap
    stub = StubRMAP()
    monkeypatch.setattr(server, "rmap", stub, raising=True)
    yield stub
    # återställ
    monkeypatch.setattr(server, "rmap", real, raising=True)


def _post_json(client, url, obj, headers=None):
    return client.post(url, data=json.dumps(obj), content_type="application/json", headers=headers or {})


# -----------------------
# /api/rmap-initiate
# -----------------------

def test_rmap_initiate_dict_payload(client, stubbed_rmap):
    raw = base64.b64encode(b"PGP-BLOCK").decode()
    r = _post_json(client, "/api/rmap-initiate", {"payload": raw})
    assert r.status_code == 200
    assert r.get_json() == {"payload": raw}


def test_rmap_initiate_str_payload(client, monkeypatch, stubbed_rmap):
    monkeypatch.setattr(stubbed_rmap, "handle_message1", lambda obj: obj.get("payload", ""), raising=True)
    raw = base64.b64encode(b"PGP-STR").decode()
    r = _post_json(client, "/api/rmap-initiate", {"payload": raw})
    assert r.status_code == 200
    assert r.get_json() == {"payload": raw}


def test_rmap_initiate_missing_payload_400(client):
    r = _post_json(client, "/api/rmap-initiate", {})
    assert r.status_code == 400
    assert "Missing 'payload'" in r.get_data(as_text=True)


# -----------------------
# /api/rmap-get-link
# -----------------------

def test_rmap_get_link_hex_string_ok(client, monkeypatch, stubbed_rmap):
    link = "0123456789abcdef" + "0011223344556677"
    monkeypatch.setattr(stubbed_rmap, "handle_message2", lambda obj: link, raising=True)
    stubbed_rmap.nonces = {"alice@example.com": (0xDEAD, int("0011223344556677", 16))}

    r = _post_json(client, "/api/rmap-get-link", {"payload": "ignored"})
    assert r.status_code == 200
    assert r.get_json()["result"] == link


def test_rmap_get_link_dict_result_ok(client, monkeypatch, stubbed_rmap):
    link = "fedcba9876543210" + "778899aabbccdde0"
    monkeypatch.setattr(stubbed_rmap, "handle_message2", lambda obj: {"result": link}, raising=True)
    stubbed_rmap.nonces = {"bob@example.com": (123, int("778899aabbccdde0", 16))}

    r = _post_json(client, "/api/rmap-get-link", {"payload": "x"})
    assert r.status_code == 200
    assert r.get_json()["result"] == link


def test_rmap_get_link_dict_nonces_int_ok(client, monkeypatch, stubbed_rmap):
    def _m2(_):
        return {"nonce_client": 0xAAAABBBBCCCCDDDD, "nonce_server": 0x0000000000000102}
    monkeypatch.setattr(stubbed_rmap, "handle_message2", _m2, raising=True)
    stubbed_rmap.nonces = {"carol@example.com": (999, 0x0000000000000102)}

    r = _post_json(client, "/api/rmap-get-link", {"payload": "y"})
    assert r.status_code == 200
    js = r.get_json()
    assert "result" in js and len(js["result"]) == 32


def test_rmap_get_link_dict_nonces_str_hex_ok(client, monkeypatch, stubbed_rmap):
    def _m2(_):
        return {"nonceClient": "0xdeadbeef", "nonceServer": "0011223344556677"}
    monkeypatch.setattr(stubbed_rmap, "handle_message2", _m2, raising=True)
    stubbed_rmap.nonces = {"dave@example.com": (int("deadbeef", 16), int("0011223344556677", 16))}

    r = _post_json(client, "/api/rmap-get-link", {"payload": "z"})
    assert r.status_code == 200
    assert len(r.get_json()["result"]) == 32


def test_rmap_get_link_invalid_hex_valueerror_400(client, monkeypatch, stubbed_rmap):
    bad = "0123456789abcdef" + "thisisnothexvalu!"
    monkeypatch.setattr(stubbed_rmap, "handle_message2", lambda obj: bad, raising=True)

    r = _post_json(client, "/api/rmap-get-link", {"payload": "p"})
    assert r.status_code == 400
    body = r.get_json()
    assert body.get("error") in {"Unexpected Message2 string", "Invalid hex in Message2 string"}
    assert bad in body.get("debug", "")


def test_rmap_get_link_missing_nonces_400(client, monkeypatch, stubbed_rmap):
    monkeypatch.setattr(stubbed_rmap, "handle_message2", lambda obj: {"foo": "bar"}, raising=True)
    r = _post_json(client, "/api/rmap-get-link", {"payload": "q"})
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "Invalid session info" in body or "Invalid Message2" in body


def test_rmap_get_link_identity_not_found_ok(client, monkeypatch, stubbed_rmap):
    stubbed_rmap.nonces = {"eve@example.com": (0x11, 0x22)}
    monkeypatch.setattr(
        stubbed_rmap,
        "handle_message2",
        lambda obj: {"nonce_client": 0xAAAABBBBCCCCDDDD, "nonce_server": 0x0000000000000102},
        raising=True,
    )

    r = _post_json(client, "/api/rmap-get-link", {"payload": "nohit"})
    assert r.status_code == 200
    js = r.get_json()
    assert "result" in js and len(js["result"]) == 32
