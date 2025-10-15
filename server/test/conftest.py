# server/test/conftest.py
import io
import random
import string
import pytest
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

# ---------- DB must be up ----------
@pytest.fixture(scope="session", autouse=True)
def db_available():
    c = app.test_client()  # own client to avoid scope-clashes
    js = (c.get("/healthz").get_json() or {})
    assert js.get("db_connected") is True, (
        "DB is not connected according to /healthz. "
        "Start DB (docker compose up -d db) or export DB_* env vars before running tests."
    )
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
def upload_sample_pdf(auth_headers):
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
