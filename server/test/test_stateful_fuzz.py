# Added this for the fuzzing specialization task /Adna
import pytest
pytestmark = pytest.mark.usefixtures("require_db")

import json
import random
import string
import uuid
import pytest
from pathlib import Path

from server import app

client = app.test_client()


def random_email():
    return f"fuzz_{uuid.uuid4().hex[:8]}@example.test"


def random_password():
    return uuid.uuid4().hex


def _extract_token(resp_json: dict):
    """
    Try to find a bearer token in common locations returned by login endpoints.
    Returns None if nothing found.
    """
    if not isinstance(resp_json, dict):
        return None
    for key in ("token", "access_token", "jwt", "auth_token", "authorization"):
        v = resp_json.get(key)
        if isinstance(v, str) and len(v) > 0:
            # if the server returned "Bearer <tok>" accept that format too
            if v.lower().startswith("bearer "):
                return v
            return "Bearer " + v

    user = resp_json.get("user")
    if isinstance(user, dict):
        for key in ("token", "access_token", "jwt"):
            v = user.get(key)
            if isinstance(v, str) and len(v) > 0:
                return "Bearer " + v
    return None


@pytest.mark.timeout(10)
def test_stateful_auth_and_list_documents():
    """
    Stateful sequence:
      1. create-user (if possible)
      2. login
      3. call list-documents with token (if obtained)
    Verifies that none of these steps cause 5xx and that authenticated endpoints respond sensibly.
    """
    email = random_email()
    password = random_password()

    # 1) Create user
    create_payload = {"email": email, "password": password}
    resp = client.post("/api/create-user", json=create_payload)
    # Accept 201 Created or 400/409 (already exists / input validation) but never 5xx
    assert resp.status_code < 500, f"/api/create-user returned 5xx: {resp.status_code} body={resp.get_data(as_text=True)[:400]}"

    # 2) Login
    resp = client.post("/api/login", json=create_payload)
    assert resp.status_code < 500, f"/api/login returned 5xx: {resp.status_code} body={resp.get_data(as_text=True)[:400]}"

    token = None
    try:
        token = _extract_token(resp.get_json(silent=True) or {})
    except Exception:
        token = None

    headers = {"Authorization": token} if token else {}

    # 3) List documents (authenticated / unauthenticated variations should not crash)
    resp = client.get("/api/list-documents", headers=headers)
    assert resp.status_code < 500, f"/api/list-documents returned 5xx: {resp.status_code}"


@pytest.mark.timeout(20)
def test_watermark_lifecycle_fuzz():
    """
    Attempt a simple watermark lifecycle:
      - Find an available document from /api/list-documents
      - POST /api/create-watermark (or /api/create-watermark/{id}) using a minimal payload that only requires key
      - POST /api/read-watermark (read back watermark metadata) using the key
    This test is defensive: if no document is found it will skip the watermark creation phase gracefully,
    but will still assert that none of the server calls return 5xx.
    """

    # create and login a user (re-use helper pattern)
    email = random_email()
    password = random_password()
    client.post("/api/create-user", json={"email": email, "password": password})
    resp = client.post("/api/login", json={"email": email, "password": password})
    assert resp.status_code < 500, f"/api/login 5xx: {resp.status_code}"

    token = None
    try:
        token = _extract_token(resp.get_json(silent=True) or {})
    except Exception:
        token = None
    headers = {"Authorization": token} if token else {}

    # list documents to get an id to work with
    resp = client.get("/api/list-documents", headers=headers)
    assert resp.status_code < 500, f"/api/list-documents 5xx: {resp.status_code}"
    docs = []
    try:
        data = resp.get_json(silent=True)
        if isinstance(data, list):
            docs = data
        elif isinstance(data, dict) and "documents" in data and isinstance(data["documents"], list):
            docs = data["documents"]
    except Exception:
        docs = []

    # try to find a numeric id in docs (defensive)
    document_id = None
    for d in docs:
        if isinstance(d, dict):
            if "id" in d:
                document_id = d["id"]
                break
            if "documentid" in d:
                document_id = d["documentid"]
                break

    # If no documents were found, still test create/read watermark endpoints with a fake id,
    # Ensure the server doesn't crash (no 5xx).
    if document_id is None:
        document_id = 1

    wm_payload = {
        "key": "testkey-" + uuid.uuid4().hex[:8],
        "secret": "maybe-secret",
        "method": "text",
        "intended_for": "fuzz-target",
        "position": random.choice((None, "bottom-right", "top-left")),
    }

    # Attempt to create watermark for a path that accepts either /api/create-watermark or /api/create-watermark/<id>
    # Try both variations; assert not 5xx.
    create_url_with_id = f"/api/create-watermark/{document_id}"
    resp1 = client.post(create_url_with_id, json=wm_payload, headers=headers)
    assert resp1.status_code < 500, f"{create_url_with_id} returned 5xx: {resp1.status_code} body={resp1.get_data(as_text=True)[:400]}"

    # Try the body-based create endpoint (without path param)
    resp2 = client.post("/api/create-watermark", json={**wm_payload, "id": document_id}, headers=headers)
    assert resp2.status_code < 500, f"/api/create-watermark returned 5xx: {resp2.status_code} body={resp2.get_data(as_text=True)[:400]}"

    # If one of the above succeeded with a JSON body giving a version id / link, try to read it back
    read_attempted = False
    for r in (resp1, resp2):
        j = r.get_json(silent=True) or {}
        # candidate keys commonly returned by create workflows
        vid = j.get("id") or j.get("version_id") or j.get("versionid") or j.get("documentid")
        link = j.get("link")
        # Try read-watermark with key + link or version id if available; otherwise attempt minimal key-only variant.
        read_payloads = []
        if vid:
            read_payloads.append({"version_id": vid, "key": wm_payload["key"]})
        if link:
            read_payloads.append({"link": link, "key": wm_payload["key"]})
        # always try key-only variant (frontend path)
        read_payloads.append({"key": wm_payload["key"]})

        for rp in read_payloads:
            resp_read = client.post("/api/read-watermark", json=rp, headers=headers)
            assert resp_read.status_code < 500, f"/api/read-watermark returned 5xx: {resp_read.status_code} payload={rp}"
            read_attempted = True

    # If none of the create calls returned useful JSON, still attempt a final key-only read to verify robustness.
    if not read_attempted:
        resp_read = client.post("/api/read-watermark", json={"key": wm_payload["key"]}, headers=headers)
        assert resp_read.status_code < 500, f"/api/read-watermark returned 5xx: {resp_read.status_code}"
