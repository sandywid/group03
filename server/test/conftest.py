from __future__ import annotations
import os
import time
import threading
import contextlib
import io
import random
import string

import pytest
import requests
from werkzeug.serving import make_server
from server import create_app

@pytest.fixture(scope="session")
def db_available():
    if not os.getenv("BASE_URL"):
        pytest.skip("DB saknas i offline-läget (kräver BASE_URL)")
    return True

# =========================
# 1) Flask-klient (session)
# =========================
@pytest.fixture(scope="session")
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


# ===============================================
# 2) Live-server (offline default, BASE_URL online)
# ===============================================
@pytest.fixture(scope="session")
def live_server():
    env_url = os.getenv("BASE_URL")
    if env_url:
        _wait_until_up(env_url, 60)
        yield env_url
        return

    host = os.getenv("TEST_HOST", "127.0.0.1")
    port = int(os.getenv("TEST_PORT", "5001"))
    url = f"http://{host}:{port}"

    app = create_app()
    app.config.update(TESTING=True)

    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        _wait_until_up(url, 60)
        yield url
    finally:
        with contextlib.suppress(Exception):
            server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


def _wait_until_up(url: str, timeout_s: int = 60):
    import requests, time
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
