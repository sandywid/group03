# server/test/test_static_security.py
import os
import sys
import types
import urllib.parse
import pytest

# Mocka watermarking_utils tidigt (så import av server inte kräver pikepdf i test)
if 'watermarking_utils' not in sys.modules:
    sys.modules['watermarking_utils'] = types.ModuleType('watermarking_utils')

from server import app  # din app har statik på "/<path>" och "/"
# Flask använder app.static_folder (default: <paket>/static)
STATIC_FOLDER = app.static_folder

@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Lägger testfiler i appens faktiska static-folder.
    Din server-route är '/<path:filename>' så vi anropar '/public.txt', inte '/static/public.txt'.
    """
    # Sätt en temporär static-folder för test
    test_static = tmp_path / "static"
    (test_static / "uploads").mkdir(parents=True, exist_ok=True)
    (test_static / "public.txt").write_text("public ok", encoding="utf-8")
    (test_static / "uploads" / "secret.txt").write_text("secret ok", encoding="utf-8")

    # Patcha appens static_folder till vår temporära katalog
    monkeypatch.setattr(app, "static_folder", os.fspath(test_static), raising=False)

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def _ok(status): return status == 200
def _blocked(status): return status in (400, 403, 404)

def test_can_fetch_normal_file(client):
    r = client.get("/public.txt")
    assert _ok(r.status_code)
    assert r.data == b"public ok"

def test_can_fetch_subdir_file(client):
    r = client.get("/uploads/secret.txt")
    assert _ok(r.status_code)
    assert r.data == b"secret ok"

def test_nonexistent_returns_not_ok(client):
    r = client.get("/nope.txt")
    assert _blocked(r.status_code)

@pytest.mark.parametrize("path", [
    "../public.txt",
    "..%2fpublic.txt",
    "%2e%2e/public.txt",
    "..\\public.txt",
    "uploads/../../public.txt",
    "uploads/%2e%2e/%2e%2e/public.txt",
])
def test_traversal_blocked(client, path):
    # send_static_file ska hålla oss inom static_folder -> 404 (eller 400/403 beroende på implementation)
    r = client.get(f"/{path}")
    assert _blocked(r.status_code)

def test_absolute_path_blocked(client, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    r = client.get("/" + os.path.abspath(outside))
    assert _blocked(r.status_code)

def test_double_slash_and_empty_segments(client):
    # Dubbla slashar kan ge 308 (redirect) eller 404 beroende på normalisering.
    r = client.get("//public.txt", follow_redirects=True)
    assert r.status_code in (200, 308, 404)
    if r.status_code == 200:
        assert r.data == b"public ok"

    r2 = client.get("/uploads//secret.txt", follow_redirects=True)
    assert r2.status_code in (200, 308, 404)
    if r2.status_code == 200:
        assert r2.data == b"secret ok"


def test_overlong_name_blocked_or_missing(client):
    long_name = "a"*300 + ".txt"
    r = client.get(f"/{long_name}")
    assert r.status_code in (404, 400, 403)

@pytest.mark.parametrize("name", [
    "före_efter-bild.pdf",
    "rapport version(1).pdf",
    "Bild-äåö—dash.pdf",
])
def test_unicode_and_special_chars_safe(client, name):
    target = os.path.join(app.static_folder, name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(b"ok")
    r = client.get("/" + name)
    assert _ok(r.status_code)
    enc = urllib.parse.quote(name)
    r2 = client.get("/" + enc)
    assert _ok(r2.status_code)

def test_null_byte_like_pattern_blocked(client):
    r = client.get("/public.txt%00.pdf")
    # Ska inte returnera "public ok" med %00-trick
    assert _blocked(r.status_code) or (r.status_code == 200 and b"public ok" not in r.data)
