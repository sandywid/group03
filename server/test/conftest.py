# conftest.py — pytest utan Docker/MariaDB: SQLite + kompatibilitet & robust ordning
import os
import io
import pathlib
import sqlite3
import pytest
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from pathlib import Path

LOG_PATH = Path("logs/app.log").absolute()
os.environ.setdefault("LOG_PATH", str(LOG_PATH))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ==========================================================
# Bas: miljö & adapters
# ==========================================================

# Stäng av rate limiting i tester
os.environ.setdefault("RATELIMIT_ENABLED", "0")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

# Gör så att sqlite3 kan binda pathlib.Path (och underklasser) som TEXT
sqlite3.register_adapter(pathlib.Path, lambda p: str(p))
if hasattr(pathlib, "PosixPath"):
    sqlite3.register_adapter(pathlib.PosixPath, lambda p: str(p))
if hasattr(pathlib, "WindowsPath"):
    sqlite3.register_adapter(pathlib.WindowsPath, lambda p: str(p))


# ==========================================================
# Klass-nivå hook: gäller ALLA Engines vid varje ny SQLite-connection
# Säkerställer att UNHEX/HEX/LAST_INSERT_ID finns oavsett ordning.
# ==========================================================
@event.listens_for(Engine, "connect")
def _sqlite_mysql_compat(dbapi_conn, _):
    # Körs även för andra DBAPI, men create_function finns på sqlite3-conn.
    try:
        dbapi_conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass

    # MariaDB-kompatibelt LAST_INSERT_ID()
    def _last_insert_id():
        cur = dbapi_conn.execute("SELECT last_insert_rowid();")
        row = cur.fetchone()
        return row[0] if row else None
    try:
        dbapi_conn.create_function("LAST_INSERT_ID", 0, _last_insert_id)
    except Exception:
        pass

    # UNHEX(str) -> bytes (tål 0x-prefix och udda längd; ogiltig hex -> NULL)
    def _unhex(val):
        if val is None:
            return None
        if isinstance(val, (bytes, bytearray)):
            return bytes(val)
        s = str(val).strip()
        if s.startswith(("0x", "0X")):
            s = s[2:]
        if len(s) % 2 == 1:
            s = "0" + s
        try:
            return bytes.fromhex(s)
        except ValueError:
            return None
    try:
        dbapi_conn.create_function("UNHEX", 1, _unhex)
    except Exception:
        pass

    # HEX(x) -> övre hexsträng, likt MySQL
    def _hex(val):
        if val is None:
            return None
        if isinstance(val, str):
            val = val.encode()
        if isinstance(val, (bytes, bytearray, memoryview)):
            return bytes(val).hex().upper()
        if isinstance(val, int):
            h = hex(val)[2:]
            if len(h) % 2 == 1:
                h = "0" + h
            return h.upper()
        return str(val).encode().hex().upper()
    try:
        dbapi_conn.create_function("HEX", 1, _hex)
    except Exception:
        pass


# ==========================================================
# Autouse app-context i alla tester (slipper "Working outside app context")
# ==========================================================
@pytest.fixture(autouse=True)
def _app_ctx():
    import server
    with server.app.app_context():
        yield


# ==========================================================
# Installera engine + schema och injicera i appen
# ==========================================================
@pytest.fixture(scope="session", autouse=True)
def _install_sqlite_engine_and_schema():
    """
    Skapa en filbaserad SQLite-engine för tester, injicera i appen,
    se till att klass-hooken ovan hinner appliceras, och skapa minimalt schema.
    """
    from server import app

    sqlite_path = pathlib.Path("test_db.sqlite").absolute()
    engine = create_engine(f"sqlite:///{sqlite_path}", future=True)

    # Konvertera Path-parametrar → str innan execute (för säkerhets skull)
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

    # Peka appen på denna engine
    app.config["_ENGINE"] = engine
    app.config["TESTING"] = True

    # Viktigt: töm poolen så att nästa connect blir "ny" och träffas av klass-hooken
    engine.dispose()

    # Minimalt schema + index
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

    # Städning
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
# Hjälpfunktioner & fixtures som testerna använder
# ==========================================================
def _rand(n=6) -> str:
    import string, random
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


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
