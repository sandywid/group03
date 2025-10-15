# flag_detection.py
import re
import time
import uuid
from flask import request, g
from logging import getLogger

logger = getLogger("app.flag_detector")

# regex för flaggformat t.ex. FLAG{...} — anpassa efter ert format
FLAG_REGEX = re.compile(r"(FLAG\{.*?\})", re.IGNORECASE)

# Lista med känsliga vägar eller param-namn att bevaka
SUSPICIOUS_PATHS = ["/flag", "/get-flag", "/”Mr_Important", "/flag.txt"]
SUSPICIOUS_PARAM_NAMES = ["flag", "”Mr_Important", "token", "key"]

def mask_flag_in_text(text: str) -> (str, bool):
    """Returnerar (masked_text, found_flag_bool). Maskar innehåll som matchar FLAG_REGEX"""
    if not text:
        return text, False
    def repl(m):
        s = m.group(1)
        # Visa bara första 6 tecken + length -> exempel "FLAG{ex...} (len=20)"
        return f"FLAG{{***}} (len={len(s)})"
    new, n = FLAG_REGEX.subn(repl, text)
    return new, n > 0

def detect_flag_attempt():
    """Kalla i before_request eller i after_request för att upptäcka försök."""
    # basic context
    g.start = time.time()
    g.request_id = str(uuid.uuid4())

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    ua = request.headers.get("User-Agent", "")
    path = request.path
    method = request.method

    found = False
    details = {"where": [], "samples": []}

    # 1) path-based detection
    if any(path.lower().startswith(p) for p in SUSPICIOUS_PATHS):
        found = True
        details["where"].append("path")

    # 2) query params
    for k, v in request.args.items():
        if k.lower() in SUSPICIOUS_PARAM_NAMES:
            masked, had = mask_flag_in_text(v)
            details["where"].append("query_param")
            details["samples"].append({"param": k, "value": masked})
            if had:
                found = True
        else:
            # detect if value itself looks like a flag
            masked, had = mask_flag_in_text(v)
            if had:
                details["where"].append("query_param_flag_pattern")
                details["samples"].append({"param": k, "value": masked})
                found = True

    # 3) body (begränsa storlek — risk för DoS genom jättestora bodies)
    try:
        raw = request.get_data(as_text=True, parse_form_data=False)[:2000]  # max 2k chars
    except Exception:
        raw = ""
    if raw:
        masked, had = mask_flag_in_text(raw)
        if had:
            found = True
            details["where"].append("body_flag_pattern")
            details["samples"].append({"body_snippet": masked})
        else:
            # kort heuristik: om body innehåller ord "flag" eller "get-flag"
            if "flag" in raw.lower() or "get-flag" in raw.lower():
                details["where"].append("body_suspicious_word")
                details["samples"].append({"body_snippet": raw[:200]})

    # 4) headers (sällsynt men kolla)
    for hk, hv in request.headers.items():
        if "flag" in hk.lower() or "flag" in (hv or "").lower():
            details["where"].append("header")
            details["samples"].append({"header": hk, "value": hv})

    if found or details["where"]:
        # Logga som strukturerad JSON via logger (konfigurera logger att skriva till stdout / fil)
        duration_ms = int((time.time() - g.start) * 1000)
        event = {
            "event": "flag_access_attempt",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": g.get("request_id"),
            "client_ip": client_ip,
            "user_agent": ua,
            "method": method,
            "path": path,
            "duration_ms": duration_ms,
            "details": details,
            # truncated headers for context (inte alla headers, bara exempel)
            "headers_sample": {
                "accept": request.headers.get("Accept"),
                "content_type": request.headers.get("Content-Type")
            }
        }
        # Anropa logger
        logger.warning(event)

        # Optionalt: returnera en markering i g för efterföljande use (t.ex. ban)
        g.flag_attempt = True
        g.flag_attempt_event = event
    else:
        g.flag_attempt = False

