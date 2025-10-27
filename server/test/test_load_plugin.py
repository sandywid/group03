# test/test_load_plugin.py
from pathlib import Path
import pickle
import pytest


# =========================
# Hjälp
# =========================
def _plugins_dir():
    import server
    storage_root = Path(server.app.config["STORAGE_DIR"])
    p = storage_root / "files" / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _write_pickle(obj, filename: str):
    dst = _plugins_dir() / filename
    with dst.open("wb") as f:
        pickle.dump(obj, f)
    return dst

def _get_methods(client):
    r = client.get("/api/get-watermarking-methods")
    assert r.status_code == 200, r.get_data(as_text=True)
    js = r.get_json() or {}
    return js.get("methods", []), js.get("count", 0)


# =========================
# Plugin-klasser (modulnivå!)
# =========================
# OBS: De måste definieras på modulnivå för att kunna pickle:as.

import server

class GoodPlugin(server.WatermarkingMethod):
    """Minimal fungerande plugin som uppfyller ABC:t."""
    name = "good-plugin"

    # Krävs av er endpoint + ABC
    def add_watermark(self, data: bytes, *, key: str, secret: str, position=None) -> bytes:
        return (data or b"") + b"::wm"

    def read_secret(self, data: bytes, *, key: str, position=None) -> str | None:
        return "secret"

    # ABC-krav (dummy-implementationer som duger)
    def is_watermark_applicable(self, *, filename: str | None = None, mimetype: str | None = None, **_) -> bool:
        # Gör det enkelt – säg att den alltid kan appliceras i test
        return True

    def get_usage(self) -> dict:
        # En enkel form som många implementationer brukar returnera
        return {
            "params": [
                {"name": "key", "type": "string", "required": True},
                {"name": "secret", "type": "string", "required": True},
                {"name": "position", "type": "string", "required": False},
            ]
        }


class BadPlugin:
    """Saknar WatermarkingMethod-API och ABC – ska nekas av endpointen."""
    pass


# =========================
# Tester
# =========================
def test_load_plugin_requires_filename(client, auth_headers):
    r = client.post("/api/load-plugin", headers=auth_headers, json={})
    assert r.status_code == 400
    assert "filename" in (r.get_json() or {}).get("error", "").lower()

@pytest.mark.parametrize("bad", ["../evil.pkl", "/abs/path.pkl", r"..\evil.pkl"])
def test_load_plugin_rejects_unsafe_filename(client, auth_headers, bad):
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": bad})
    assert r.status_code == 400
    assert "invalid" in (r.get_json() or {}).get("error", "").lower()

def test_load_plugin_missing_file_404(client, auth_headers):
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "nope.pkl"})
    assert r.status_code == 404

def test_load_plugin_invalid_pickle_400(client, auth_headers):
    dst = _plugins_dir() / "broken.pkl"
    dst.write_bytes(b"not a pickle")
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "broken.pkl"})
    assert r.status_code == 400
    assert "failed" in (r.get_json() or {}).get("error", "").lower()

def test_load_plugin_bad_plugin_api_400(client, auth_headers):
    _write_pickle(BadPlugin, "bad.pkl")
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "bad.pkl"})
    assert r.status_code == 400
    assert "does not implement" in (r.get_json() or {}).get("error", "").lower()

def test_load_plugin_success_with_class_pickle(client, auth_headers):
    # Pickla själva klassen (modulnivå-klass → picklebar)
    _write_pickle(GoodPlugin, "good_class.pkl")

    before_methods, before_count = _get_methods(client)
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "good_class.pkl"})
    assert r.status_code in (200, 201), r.get_data(as_text=True)

    methods, count = _get_methods(client)
    names = {m["name"] for m in methods}
    assert ("good-plugin" in names) or ("GoodPlugin" in names)
    assert count >= before_count

def test_load_plugin_success_with_instance_pickle(client, auth_headers):
    # Pickla en instans av klassen
    _write_pickle(GoodPlugin(), "good_instance.pkl")
    r = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "good_instance.pkl"})
    assert r.status_code in (200, 201), r.get_data(as_text=True)

def test_load_plugin_idempotent_same_name_does_not_increase_count(client, auth_headers):
    # Ladda en första gång
    _write_pickle(GoodPlugin, "same_name.pkl")
    r1 = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "same_name.pkl"})
    assert r1.status_code in (200, 201)

    # Läs count
    _, before = _get_methods(client)

    # Ladda samma igen – endpointen kan svara 200/201/400 beroende på implementering,
    # men antalet registrerade metoder ska inte öka.
    r2 = client.post("/api/load-plugin", headers=auth_headers, json={"filename": "same_name.pkl"})
    assert r2.status_code in (200, 201, 400)

    _, after = _get_methods(client)
    assert after == before

def test_load_plugin_requires_auth(client):
    r = client.post("/api/load-plugin", json={"filename": "x.pkl"})
    assert r.status_code in (401, 403)
