# server/test/conftest.py
import os, pathlib
import io
import random
import string
import pytest

# --- turn off rate limiting BEFORE importing the app ---
os.environ.setdefault("RATELIMIT_ENABLED", "0")       
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://") 

try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).resolve().parents[2] / ".env", override=False)
except Exception:
    pass

# default DB_* if missing, and map MARIADB_* => DB_*
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_NAME", "tatou")
if "DB_USER" not in os.environ and "MARIADB_USER" in os.environ:
    os.environ["DB_USER"] = os.environ["MARIADB_USER"]
if "DB_PASSWORD" not in os.environ and "MARIADB_PASSWORD" in os.environ:
    os.environ["DB_PASSWORD"] = os.environ["MARIADB_PASSWORD"]

from server import app

# ---------- Helpers ----------
def _rand(n=6):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

# ---------- Test mode (disable rate limiting) ----------
@pytest.fixture(scope="session", autouse=True)
def configure_app_for_tests():
    app.config.update(
        TESTING=True,
        RATELIMIT_ENABLED=False,
        RATELIMIT_STORAGE_URI="memory://",
    )
    # hard-disable an already-initialized limiter (if present)
    lim = getattr(app, "extensions", {}).get("limiter")
    if lim:
        try:
            lim.enabled = False
        except Exception:
            pass

# --- Detect DB once, without failing the whole session ---
HAS_DB = None

@pytest.fixture(scope="session", autouse=True)
def detect_db():
    """Detect DB availability once and store the result."""
    global HAS_DB
    js = (app.test_client().get("/healthz").get_json() or {})
    HAS_DB = bool(js.get("db_connected"))
    if not HAS_DB:
        print("\n[tests] DB not connected: tests marked 'requires_db' will be skipped.")
    return HAS_DB

@pytest.fixture(scope="session")
def require_db():
    """Use in tests that need the DB."""
    if not HAS_DB:
        pytest.skip("DB not connected")

# --- Back-compat so old fixtures keep working ---
@pytest.fixture(scope="session")
def db_available(require_db):
    return True

# ---------- HTTP client (function scope so it plays nice with other tests) ----------
@pytest.fixture(scope="function")
def client():
    return app.test_client()

# --- Auth ---
@pytest.fixture(scope="session")
def auth_token(db_available):
    c = app.test_client()
    # creates one sable test user per testrun
    import random, string
    suf = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    email = f"{suf}@example.test"
    pwd = "Passw0rd!"
    c.post("/api/create-user", json={"login": suf, "email": email, "password": pwd})
    js = c.post("/api/login", json={"email": email, "password": pwd}).get_json() or {}
    assert "token" in js, f"login failed: {js}"
    return js["token"]

@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

# ---------- Test data ----------
@pytest.fixture
def tiny_valid_pdf_bytes():
    # minimal valid PDF
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"

# ONE upload for each test run, with THE SAME user as auth_headers
@pytest.fixture(scope="session")
def upload_sample_pdf(auth_headers, require_db):
    c = app.test_client()
    import io
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    data = {"file": (io.BytesIO(pdf_bytes), "report.pdf"), "name": "report.pdf"}
    r = c.post("/api/upload-document",
               headers=auth_headers,
               data=data,
               content_type="multipart/form-data")
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()
