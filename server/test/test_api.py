from pathlib import Path
import sys

# funkar både om du kör från group03/ eller server/
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from server import create_app  # från server/src/server.py

app = create_app()

def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.is_json
