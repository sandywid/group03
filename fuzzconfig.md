0) Prereqs
# From repo root
python -m venv server/.venv
source server/.venv/bin/activate

pip install "schemathesis[pytest]" hypothesis

1) Project files used

OpenAPI spec: openapi.yaml (repo root)

Tests:

server/test/test_fuzz_schemathesis.py ← OpenAPI-based fuzzing

server/test/test_extra_fuzz.py ← targeted fuzz (tokens, traversal, large inputs)

server/test/test_stateful_fuzz.py ← short stateful flows

server/test/test_fuzz_upload.py ← PDF mutation fuzzing

server/test/test_public_endpoints.py ← public sanity

server/test/test_static_security.py ← static file + traversal

server/test/test_security_authorization.py ← basic authz isolation

server/test/test_regressions.py ← non-regression tests for fixed bugs

2) Docker
# From repo root
docker compose up --build -d
# Wait until DB is healthy:
docker compose ps

3) Environment
# Optional: deterministic fuzzing
export HYPOTHESIS_SEED=123

4) Run test suites
A) Full campaign (all tests)
LOG_PATH=logs/app.log python -m pytest -q server/test

B) Verbose + JUnit (CI-style)
LOG_PATH=logs/app.log \
python -m pytest -vv server/test --junitxml=reports/junit.xml

C) Only OpenAPI fuzzer
LOG_PATH=logs/app.log \
python -m pytest -q server/test/test_fuzz_schemathesis.py

D) Only regression tests
LOG_PATH=logs/app.log \
python -m pytest -q server/test/test_regressions.py

E) Multiple seeded fuzz rounds
for s in 111 222 333 444 555; do
  HYPOTHESIS_SEED=$s LOG_PATH=logs/app.log \
  python -m pytest -q server/test/test_fuzz_schemathesis.py -k test_api_fuzz || break
done

5) What each suite does

test_fuzz_schemathesis.py → fuzzes all operations from openapi.yaml and asserts no 5xx.

test_extra_fuzz.py → invalid tokens, path traversal, extreme /api/login inputs.

test_regressions.py → locks fixes:

/api/login returns 400 for non-object JSON (e.g., ["oops"]).

/api/read-watermark only requires key.

uploads validate type/name and avoid traversal.

test_stateful_fuzz.py → short flows: create → login → list; watermark lifecycle.

test_fuzz_upload.py → PDF mutation fuzz.

test_static_security.py → static traversal & unicode safety.

test_public_endpoints.py → public routes behave sanely.

test_security_authorization.py → owner isolation checks.

6) Handy commands
LOG_PATH=logs/app.log python -m pytest -q server/test -vv

HYPOTHESIS_SEED=123 LOG_PATH=logs/app.log pytest -vv server/test --junitxml=reports/junit.xml

HYPOTHESIS_SEED=123 LOG_PATH=logs/app.log pytest -vv server/test/test_fuzz_schemathesis.py   
