# used to be in server/test/conftest.py (Sandras upload) changed to tests_live.py and changed conftest.py /Adna
# server/test/tests_live.py
import os
import time
import threading
import contextlib
import requests
import pytest
from werkzeug.serving import make_server
from server import create_app

# --- 1) Flask testklient (ingen nätverkstrafik) ---
@pytest.fixture
def client():
    app = create_app()                 # inga args
    app.config.update(TESTING=True)    # uppdatera efteråt
    with app.test_client() as c:
        yield c

# --- 2) Live server (offline som default, BASE_URL om satt) ---
@pytest.fixture(scope="session")
def live_server():
    env_url = os.getenv("BASE_URL")
    if env_url:
        _wait_until_up(env_url, timeout_s=60)
        yield env_url
        return

    host = os.getenv("TEST_HOST", "127.0.0.1")
    port = int(os.getenv("TEST_PORT", "5001"))
    url = f"http://{host}:{port}"

    app = create_app()                 # inga args
    app.config.update(TESTING=True)    # säkra testläge

    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        _wait_until_up(url, timeout_s=60)
    except Exception:
        with contextlib.suppress(Exception):
            server.shutdown()
        thread.join(timeout=5)
        pytest.fail(f"Tjänsten svarade inte på {url} inom 60s")

    try:
        yield url
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        thread.join(timeout=5)

# --- 3) Bas-URL som HTTP-tester använder ---
@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server

# --- Hjälpare ---
def _wait_until_up(url: str, timeout_s: int = 60):
    deadline = time.time() + timeout_s
    health = url.rstrip("/") + "/healthz"
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(health, timeout=1)
            if r.status_code < 500:
                return
        except Exception as e:
            last_err = e
        time.sleep(1)
    raise RuntimeError(f"Tjänsten svarade inte på {url} inom {timeout_s}s; sista fel: {last_err}")