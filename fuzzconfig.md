## Instructions

```bash
cd group03/server

# Create a python virtual environement
python3 -m venv .venv

# Activate your virtual environement
. .venv/bin/activate

# Install the necessary dependencies
python -m pip install -e ".[dev]"

```

## Project files used

OpenAPI spec: openapi.yaml (repo root)

## Tests:

server/test/test_fuzz_schemathesis.py ← OpenAPI-based fuzzing

server/test/test_extra_fuzz.py ← targeted fuzz (tokens, traversal, large inputs)

server/test/test_stateful_fuzz.py ← short stateful flows

server/test/test_fuzz_upload.py ← PDF mutation fuzzing

server/test/test_public_endpoints.py ← public sanity

server/test/test_static_security.py ← static file + traversal

server/test/test_security_authorization.py ← basic authz isolation

server/test/test_regressions.py ← non-regression tests for fixed bugs

## From root directory 
```bash
cd .. # Go back to root directory (group03)

docker compose up --build -d # Rebuild the docker image and deploy the containers, make sure that you have deployed tatou correctly and set the env variables
```

## Environment
Optional: deterministic fuzzing
```bash
export HYPOTHESIS_SEED=123
```

## Run test suites
```bash
# Full campaign (all tests)
LOG_PATH=logs/app.log python -m pytest -q server/test

# Verbose + JUnit (CI-style)
LOG_PATH=logs/app.log \
python -m pytest -vv server/test --junitxml=reports/junit.xml

# Only OpenAPI fuzzer
LOG_PATH=logs/app.log \
python -m pytest -q server/test/test_fuzz_schemathesis.py

# Only regression tests
LOG_PATH=logs/app.log \
python -m pytest -q server/test/test_regressions.py

# Multiple seeded fuzz rounds
for s in 111 222 333 444 555; do
  HYPOTHESIS_SEED=$s LOG_PATH=logs/app.log \
  python -m pytest -q server/test/test_fuzz_schemathesis.py -k test_api_fuzz || break
done
```

## What each suite does

test_fuzz_schemathesis.py → fuzzes all operations from openapi.yaml and asserts no 5xx.

test_extra_fuzz.py → invalid tokens, path traversal, extreme /api/login inputs.

test_regressions.py → locks fixes:

test_stateful_fuzz.py → short flows: create → login → list; watermark lifecycle.

test_fuzz_upload.py → PDF mutation fuzz.

test_static_security.py → static traversal & unicode safety.

test_public_endpoints.py → public routes behave sanely.

test_security_authorization.py → owner isolation checks.
