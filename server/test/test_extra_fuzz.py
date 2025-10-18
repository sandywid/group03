# Added this for the fuzzing specialization task /Adna
import pytest
pytestmark = pytest.mark.usefixtures("require_db")

import pytest
import json
import random
import string
from hypothesis import given, strategies as st

# Reuse Flask app from the existing server
from server import app

client = app.test_client()


# Fuzz invalid and tampered JWT tokens (auth robustness)
INVALID_TOKENS = [
    "",  # empty
    "Bearer",  # incomplete
    "Bearer abc.def.ghi",  # wrong format
    "Bearer " + "A" * 5000,  # oversized token
    "Bearer eyJ1aWQiOiAiZGVsZXRlIiwgImVtYWlsIjogInhAYi5jIn0=.BAD",  # invalid signature
]

@pytest.mark.parametrize("token", INVALID_TOKENS)
def test_fuzz_invalid_tokens(token):
    """Ensure server never crashes on malformed or tampered JWT tokens."""
    headers = {"Authorization": token}
    resp = client.get("/api/list-documents", headers=headers)
    assert resp.status_code < 500, f"Server crashed on token: {token!r}"


# Path traversal & Unicode fuzzing on document endpoints
PATH_FUZZ = [
    "../../../etc/passwd",
    "/../../../../secret",
    "%2e%2e%2fetc/passwd",
    "documents/🦄",
    "💾💾💾",
]

@pytest.mark.parametrize("doc_id", PATH_FUZZ)
def test_fuzz_path_traversal(doc_id):
    """Ensure no directory traversal or Unicode errors occur."""
    url = f"/api/get-document/{doc_id}"
    resp = client.get(url)
    assert resp.status_code != 500, f"Path traversal crash for {doc_id}"


# Very large input fuzz on login payload
@given(
    email=st.text(min_size=0, max_size=2000),
    password=st.text(min_size=0, max_size=2000),
)
def test_login_massive_input(email, password):
    """Ensure /api/login never crashes on extreme string inputs."""
    payload = {"email": email, "password": password}
    resp = client.post("/api/login", json=payload)
    assert resp.status_code < 500


# Randomized malformed JSON bodies for create-user
MALFORMED_JSONS = [
    None,
    "not a dict",
    [],
    [1, 2, 3],
    {"email": None},
    {"email": 123, "password": True},
    {"": "x"},
    json.dumps({"nested": {"a": "b"}}),  # double encoded
]

@pytest.mark.parametrize("body", MALFORMED_JSONS)
def test_create_user_malformed_json(body):
    """Ensure /api/create-user returns 4xx and not 5xx for malformed payloads."""
    headers = {"Content-Type": "application/json"}
    resp = client.post("/api/create-user", data=json.dumps(body) if not isinstance(body, str) else body, headers=headers)
    assert resp.status_code < 500
