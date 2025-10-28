from pathlib import Path
import tempfile
from flask import Flask
import importlib

def test__ensure_dirs_executes_and_creates_versions():
    server_mod = importlib.import_module("server")  # viktigt: samma väg som övriga tester

    # Säkerställ att vi verkligen kör rätt fil
    assert server_mod._ensure_dirs.__code__.co_filename.replace("\\", "/").endswith("/src/server.py")

    with tempfile.TemporaryDirectory() as tmpdir:
        app = Flask(__name__)
        app.config["STORAGE_DIR"] = tmpdir
        versions_path = Path(tmpdir) / "versions"
        assert not versions_path.exists()

        with app.app_context():
            server_mod._ensure_dirs()

        assert versions_path.exists() and versions_path.is_dir()
