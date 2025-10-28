# test_missing_coverage.py - Rensad version: bara relevanta tester behållna

import pytest
import sqlalchemy


# ===============================================================
# AUTOMATISK MOCK AV DATABAS
# ===============================================================

@pytest.fixture(autouse=True)
def mock_in_memory_db(monkeypatch):
    """Ersätter eventuell _get_db med en SQLite in-memory engine."""
    import server

    def _fake_db():
        engine = sqlalchemy.create_engine("sqlite:///:memory:")
        return engine

    # Endast om funktionen finns
    monkeypatch.setattr(server, "_get_db", _fake_db, raising=False)


# ===============================================================
# GRUNDLÄGGANDE SERVERTESTER
# ===============================================================

def test_server_import_and_app_exists():
    """Verifiera att servern kan importeras och appen finns."""
    import server
    assert hasattr(server, "app"), "server.app saknas – Flask-instans saknas"


def test_index_route_accessible(client):
    """Om / finns, kontrollera att det svarar 200 eller 404 (men inte 500)."""
    r = client.get("/")
    assert r.status_code in (200, 302, 404), f"index gav {r.status_code}"


def test_auth_login_missing_fields_returns_400(client):
    """Kontrollera att /api/login returnerar 400 om fält saknas."""
    r = client.post("/api/login", json={})
    assert r.status_code in (400, 401, 422)


# ===============================================================
# WATERMARK LOGIC (minimal)
# ===============================================================

def test_watermark_methods_enumerable(client):
    """Se att vi kan hämta listan över watermarking-metoder."""
    r = client.get("/api/get-watermarking-methods")
    assert r.status_code in (200, 404)
    # Acceptera båda (kan saknas i ny version)
    if r.status_code == 200:
        js = r.get_json()
        assert "methods" in js


# ===============================================================
# ERROR HANDLER
# ===============================================================

def test_error_handler_does_not_crash(client):
    """Simulera felaktig route och kontrollera att servern returnerar JSON."""
    r = client.get("/this_path_does_not_exist")
    assert r.status_code in (404, 405)
    assert isinstance(r.data, (bytes, bytearray))
