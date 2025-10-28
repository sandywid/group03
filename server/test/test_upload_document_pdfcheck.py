# test/test_upload_document_pdfcheck.py
import io
import os
import importlib
from pathlib import Path
from werkzeug.datastructures import FileStorage
from flask import Flask, g
import pytest

# Logg dit vi har rättigheter
Path("logs").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LOG_PATH", str(Path("logs/app.log").absolute()))

ROUTE_PATH = "/api/upload-document"  # rätt endpoint

def _import_server():
    try:
        return importlib.import_module("server")
    except ModuleNotFoundError:
        return importlib.import_module("src.server")

def _get_app(server_mod) -> Flask:
    if hasattr(server_mod, "create_app"):
        try:
            app = server_mod.create_app()
        except TypeError:
            app = server_mod.create_app(None)
    else:
        app = getattr(server_mod, "app")
    app.config.update(TESTING=True)
    return app

def _unwrap(view_fn):
    seen = set()
    while hasattr(view_fn, "__wrapped__") and view_fn not in seen:
        seen.add(view_fn)
        view_fn = view_fn.__wrapped__  # type: ignore[attr-defined]
    return view_fn

def _load_app_and_view():
    server = _import_server()
    app = _get_app(server)

    endpoint = None
    for rule in app.url_map.iter_rules():
        if rule.rule == ROUTE_PATH and "POST" in rule.methods:
            endpoint = rule.endpoint
            break
    assert endpoint, f"Hittade ingen POST-route på {ROUTE_PATH}"
    view_fn = _unwrap(app.view_functions[endpoint])
    return app, view_fn

def _call_upload(app: Flask, view_fn, file_storage: FileStorage, storage_dir: Path):
    """
    Kör view:n direkt i request-context. Sätter g.user och STORAGE_DIR.
    Returnerar alltid ett Response-objekt.
    """
    data = {"file": file_storage}
    with app.test_request_context(
        ROUTE_PATH, method="POST", data=data, content_type="multipart/form-data"
    ):
        # Mocka auth och storage
        g.user = {"login": "testusermednyttnamn"}          # behövs av koden
        app.config["STORAGE_DIR"] = storage_dir # används för att spara filer
        resp = view_fn()                         # kan vara Response eller (json, status)
        resp = app.make_response(resp)           # normalisera till Response
    return resp

@pytest.fixture
def app_and_view():
    return _load_app_and_view()

def test_empty_filename_returns_400(tmp_path, app_and_view):
    app, view_fn = app_and_view
    fs = FileStorage(stream=io.BytesIO(b""), filename="", content_type="application/pdf")
    resp = _call_upload(app, view_fn, fs, tmp_path)
    assert resp.status_code == 400
    assert "empty filename" in (resp.get_json() or {}).get("error", "").lower()

def test_wrong_extension_returns_400(tmp_path, app_and_view):
    app, view_fn = app_and_view
    fs = FileStorage(
        stream=io.BytesIO(b"%PDF-1.4\n%%EOF\n"),
        filename="model.pkl",
        content_type="application/pdf",  # rätt mimetype för att isolera suffix-check
    )
    resp = _call_upload(app, view_fn, fs, tmp_path)
    assert resp.status_code == 400
    assert "wrong extension" in resp.get_json().get("error", "").lower()

def test_wrong_mimetype_returns_400(tmp_path, app_and_view):
    app, view_fn = app_and_view
    fs = FileStorage(
        stream=io.BytesIO(b"%PDF-1.4\n%%EOF\n"),
        filename="doc.pdf",                   # rätt suffix
        content_type="application/octet-stream",  # fel mimetype
    )
    resp = _call_upload(app, view_fn, fs, tmp_path)
    assert resp.status_code == 400
    assert "wrong mimetype" in resp.get_json().get("error", "").lower()

def test_valid_pdf_passes_pdf_checks(tmp_path, app_and_view):
    app, view_fn = app_and_view
    fs = FileStorage(
        stream=io.BytesIO(b"%PDF-1.4\n...\n%%EOF\n"),
        filename="ok.pdf",
        content_type="application/pdf",
    )
    resp = _call_upload(app, view_fn, fs, tmp_path)
    # Vi vet inte exakt OK-svar här; poängen är att inte fastna i pdf-checkarna ovan
    assert resp.status_code != 400
