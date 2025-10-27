# conftest.py — pytest utan Docker/MariaDB: SQLite + kompatibilitetsfunktioner
import os
import io
import random
import string
import pathlib
import sqlite3
import pytest
from sqlalchemy import create_engine, text, event

# Gör så att sqlite3 kan binda pathlib.Path som TEXT
# Bas-klassen (bra att behålla)
sqlite3.register_adapter(pathlib.Path, lambda p: str(p))

# Viktigt: registrera underklasser också
if hasattr(pathlib, "PosixPath"):
    sqlite3.register_adapter(pathlib.PosixPath, lambda p: str(p))
if hasattr(pathlib, "WindowsPath"):
    sqlite3.register_adapter(pathlib.WindowsPath, lambda p: str(p))

# Stäng av rate limiting i tester
os.environ.setdefault("RATELIMIT_ENABLED", "0")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# ==========================================================
# Engine + schema
# ==========================================================

@pytest.fixture(scope="session", autouse=True)
def _install_sqlite_engine_and_schema():
    """
    Skapa en SQLite-engine för tester, lägg till en MariaDB-kompatibel
    LAST_INSERT_ID(), initiera ett minimalt schema, och injicera engine i appen.
    """
    from server import app

    sqlite_path = pathlib.Path("test_db.sqlite").absolute()
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)

    # -- Fångar alla queries och konverterar Path-objekt till str innan execute --
    @event.listens_for(engine, "before_cursor_execute")
    def _coerce_path_params(conn, cursor, statement, parameters, context, executemany):
        def coerce(v):
            return str(v) if isinstance(v, pathlib.Path) else v

        # executemany med sekvens av paramset
        if isinstance(parameters, (list, tuple)) and parameters and isinstance(parameters[0], (list, tuple, dict)):
            new_params = []
            for p in parameters:
                if isinstance(p, dict):
                    new_params.append({k: coerce(v) for k, v in p.items()})
                else:
                    new_params.append(tuple(coerce(v) for v in p))
            context.parameters = new_params
            return

        # single execute: dict eller tuple/list
        if isinstance(parameters, dict):
            context.parameters = {k: coerce(v) for k, v in parameters.items()}
        elif isinstance(parameters, (list, tuple)):
            context.parameters = tuple(coerce(v) for v in parameters)

    # -- Kompatibilitet för MariaDB-saker (LAST_INSERT_ID osv.) --
    @event.listens_for(engine, "connect")
    def _sqlite_on_connect(dbapi_conn, _):
        try:
            dbapi_conn.execute("PRAGMA foreign_keys=ON;")
        except Exception:
            pass

        def _last_insert_id():
            cur = dbapi_conn.execute("SELECT last_insert_rowid();")
            row = cur.fetchone()
            return row[0] if row else None

        dbapi_conn.create_function("LAST_INSERT_ID", 0, _last_insert_id)

    # Injicera engine i appen så server.py använder denna istället
    app.config["_ENGINE"] = engine
    app.config["TESTING"] = True

    # Skapa schema
    ddl = [
        "DROP TABLE IF EXISTS Versions;",
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            login TEXT NOT NULL UNIQUE,
            hpassword TEXT NOT NULL,
            creation DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS Documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            ownerid INTEGER NOT NULL,
            sha256 BLOB NOT NULL,
            size INTEGER NOT NULL,
            creation DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS Versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documentid INTEGER NOT NULL,
            link TEXT NOT NULL,
            intended_for TEXT,
            secret TEXT,
            method TEXT,
            position TEXT,
            path TEXT NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_users_email ON Users(email);",
        "CREATE INDEX IF NOT EXISTS idx_users_login ON Users(login);",
        "CREATE INDEX IF NOT EXISTS idx_docs_owner ON Documents(ownerid);",
        "CREATE INDEX IF NOT EXISTS idx_versions_doc ON Versions(documentid);",
        "CREATE INDEX IF NOT EXISTS idx_versions_link ON Versions(link);",
    ]

    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))

    yield

    try:
        engine.dispose()
        if sqlite_path.exists():
            sqlite_path.unlink()
    except Exception:
        pass


# ==========================================================
# Test client
# ==========================================================

@pytest.fixture(scope="function")
def client():
    from server import app
    return app.test_client()


# ==========================================================
# Hjälpfunktioner
# ==========================================================

def _rand(n=6) -> str:
    import string, random
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


# ==========================================================
# Fixtures som testerna använder
# ==========================================================

@pytest.fixture(scope="session")
def auth_token():
    """Skapa en test-user via API och hämta bearer token."""
    from server import app
    c = app.test_client()

    login = _rand()
    email = f"{login}@example.test"
    pwd = "Passw0rd!"

    r = c.post("/api/create-user", json={"login": login, "email": email, "password": pwd})
    assert r.status_code in (200, 201), r.get_data(as_text=True)

    js = c.post("/api/login", json={"email": email, "password": pwd}).get_json() or {}
    assert "token" in js, f"login failed: {js}"
    return js["token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def tiny_valid_pdf_bytes():
    """Returnera ett filobjekt (BytesIO) som är en minimal PDF."""
    return io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")


@pytest.fixture(scope="session")
def upload_sample_pdf(auth_headers):
    """Ladda upp ett litet PDF-prov en gång per testsession och returnera Response-objektet."""
    from server import app
    c = app.test_client()
    pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    data = {"file": (pdf_io, "report.pdf"), "name": "report.pdf"}
    r = c.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 201, 202), r.get_data(as_text=True)
    return r  # returnera hela Response-objektet


@pytest.fixture(scope="session")
def require_db():
    """Behålls om era tester använder den som markör."""
    return True
