# Added this for the fuzzing specialization task /Adna
#server/test/test_fuzz_schemathesis.py
import os
import pathlib
import pytest
import importlib
import threading
from werkzeug.serving import make_server

# Sets logpath early
os.environ.setdefault("LOG_PATH", "logs/app.log")
os.makedirs(os.path.dirname(os.environ["LOG_PATH"]), exist_ok=True)

# Find openapi.yaml/.yml in root or docs/
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
for cand in [ROOT / "openapi.yaml", ROOT / "openapi.yml", ROOT / "docs" / "openapi.yaml", ROOT / "docs" / "openapi.yml"]:
    if cand.exists():
        OPENAPI_PATH = str(cand)
        break
else:
    raise FileNotFoundError("Hittar inte openapi.yaml/yml i projektroten eller docs/.")

# Schemathesis compatibility shim
import schemathesis as st

def _load_schema_from_path(path: str):
    # Try new-style: schemathesis.openapi.from_path
    try:
        st_openapi = getattr(st, "openapi", None)
        if st_openapi and hasattr(st_openapi, "from_path"):
            return st_openapi.from_path(path)
    except Exception:
        pass

    # Try older top-level helper
    try:
        if hasattr(st, "from_path"):
            return st.from_path(path)
    except Exception:
        pass

    # Try internal loaders (varies by version)
    try:
        loaders = importlib.import_module("schemathesis.openapi.loaders")
        if hasattr(loaders, "from_path"):
            return loaders.from_path(path)
    except Exception:
        pass

    # Fallback: load YAML then from_dict
    import yaml
    with open(path, "rb") as f:
        spec = yaml.safe_load(f)

    st_openapi = getattr(st, "openapi", None)
    if hasattr(st, "from_dict"):
        return st.from_dict(spec)
    if st_openapi and hasattr(st_openapi, "from_dict"):
        return st_openapi.from_dict(spec)

    raise RuntimeError("Kunde inte ladda OpenAPI-specen med kända API:n.")

schema = _load_schema_from_path(OPENAPI_PATH)
# end shim

from server import app  # noqa: E402

from schemathesis.checks import not_a_server_error
from hypothesis import settings
from schemathesis.checks import not_a_server_error


# Public endpoints (no auth)
PUBLIC_PREFIXES = (
    "/healthz",
    "/api/get-watermarking-methods",
    "/api/get-version/",
)

def _needs_auth(case) -> bool:
    return not any(case.operation.path.startswith(pref) for pref in PUBLIC_PREFIXES)

# Live testserver through Werkzeug (no external server is needed)
@pytest.fixture(scope="session", autouse=True)
def live_server():
    host, port = "127.0.0.1", 5005
    httpd = make_server(host, port, app)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        t.join(timeout=5)

# Basic generative fuzzing
@pytest.mark.usefixtures("require_db")
@schema.parametrize()
@settings(max_examples=75, deadline=None)
def test_api_fuzz(case, auth_headers, live_server):
    if _needs_auth(case):
        case.headers = {**(case.headers or {}), **auth_headers}
    case.call_and_validate(
        base_url=live_server,
        checks=(not_a_server_error,),
    )


    # Let Schemathesis make HTTP-calls against the little testserver
    resp = case.call(base_url=live_server, headers=case.headers)

    # Focus: no servercrashes
    assert resp.status_code < 500, (
        f"Server 5xx: {resp.status_code} for {case.operation.method} {case.operation.path}\n"
        f"Body: {getattr(resp, 'text', '')[:300]}"
    )

# Figure out if this Schemathesis version supports stateful tests
try:
    STATEFUL_DECORATOR = getattr(schema, "stateful_test", None)
except Exception:
    STATEFUL_DECORATOR = None

# Stateful fuzzing workflow
if STATEFUL_DECORATOR:
    @STATEFUL_DECORATOR
    @settings(max_examples=25, deadline=None)
    class TestTatouWorkflow:
        def setup(self):
            self.token = None

        def test_create_user(self, case, live_server):
            if case.path == "/api/create-user":
                return case.call_and_validate(base_url=live_server, checks=(not_a_server_error,))

        def test_login(self, case, live_server):
            if case.path == "/api/login":
                response = case.call_and_validate(base_url=live_server, checks=(not_a_server_error,))
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        token = data.get("token") or data.get("access_token")
                        if token:
                            self.token = f"Bearer {token}"
                except Exception:
                    pass
                return response

        def test_list_documents(self, case, live_server):
            if case.path == "/api/list-documents":
                if self.token:
                    case.headers = {"Authorization": self.token}
                return case.call_and_validate(base_url=live_server, checks=(not_a_server_error,))
else:
    @pytest.mark.skip(reason="Schemathesis stateful tests are not available in this version")
    def test_stateful_unavailable():
        pass

# Stateful fuzzing
import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine

try:
    # Schemathesis >= 3.x experimental stateful API
    from schemathesis.experimental.openapi import stateful as st_stateful
except Exception:  # pragma: no cover
    st_stateful = None


@pytest.mark.skipif(st_stateful is None, reason="schemathesis.experimental stateful API not available")
def test_stateful_workflow(live_server):
    # Build a state machine from the SAME `schema` defined above
    StateMachine = st_stateful.create_state_machine(schema)

    # Make test server base URL available to the machine (Schemathesis will read it)
    StateMachine.shared_context = {
        "base_url": live_server,
        # Default headers to try on authenticated endpoints
        "default_headers": {},
    }

    # Tune how hard this test runs
    StateMachine.settings = settings(max_examples=25, deadline=None)

    # Run the machine
    RuleBasedStateMachine.run(StateMachine)
