# create_and_download_versions.py
import requests
import json
from pathlib import Path
import time

print("╔═══════════════════════════════════════════════════╗")
print("║   VERSION CREATOR - Tatou Watermark Generator    ║")
print("╚═══════════════════════════════════════════════════╝\n")

# Konfiguration
EMAIL = "me@example.com"
USERNAME = "me"
PASSWORD = "hej"

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
output_dir = Path("downloaded_versions")
output_dir.mkdir(exist_ok=True)

# ============================================================
# HJÄLPFUNKTIONER
# ============================================================

def create_user(server):
    """Skapar en ny användare"""
    url = f"http://{server}:5000/api/create-user"
    data = {
        "email": EMAIL,
        "login": USERNAME,
        "password": PASSWORD
    }
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 201:
            return True, "Användare skapad"
        elif response.status_code == 409:
            return True, "Användare finns redan"
        else:
            return False, f"Fel: {response.status_code}"
    except Exception as e:
        return False, f"Fel: {e}"

def login(server):
    """Loggar in och får token"""
    url = f"http://{server}:5000/api/login"
    data = {
        "email": EMAIL,
        "password": PASSWORD
    }
    try:
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            token = response.json().get('token')
            return token, None
        else:
            return None, f"Login misslyckades: {response.status_code}"
    except Exception as e:
        return None, f"Fel: {e}"

def get_watermarking_methods(server, token):
    """Hämtar tillgängliga watermarking-metoder"""
    url = f"http://{server}:5000/api/get-watermarking-methods"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            methods = response.json().get('methods', [])
            if methods:
                return methods[0]['name']
        return None
    except:
        return None

def create_watermark(server, token, doc_id, intended_for, method):
    """Skapar en watermark-version av ett dokument"""
    url = f"http://{server}:5000/api/create-watermark/{doc_id}"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "method": method,
        "intended_for": intended_for,
        "secret": f"secret_{doc_id}_{intended_for}",
        "key": "my_secret_key_123"
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        if response.status_code == 201:
            return True, response.json()
        else:
            return False, f"Status {response.status_code}"
    except Exception as e:
        return False, f"Fel: {e}"

def download_version(server, link):
    """Laddar ner en watermarkad version via dess link"""
    url = f"http://{server}:5000/api/get-version/{link}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.content
        return None
    except:
        return None

# ============================================================
# HUVUDPROGRAM
# ============================================================

all_results = {}
total_versions_created = 0
total_files_downloaded = 0

for server in servers:
    print(f"\n{'═'*60}")
    print(f"📡 Server: {server}")
    print(f"{'═'*60}")
    
    server_results = {
        "login_success": False,
        "method": None,
        "versions": []
    }
    
    # Steg 1: Skapa användare (om behövs)
    print("  🔧 Skapar/verifierar användare...", end=" ")
    success, msg = create_user(server)
    print(msg)
    
    # Steg 2: Logga in
    print("  🔑 Loggar in...", end=" ")
    token, error = login(server)
    if not token:
        print(f"✗ {error}")
        all_results[server] = server_results
        continue
    print("✓ Inloggad")
    server_results["login_success"] = True
    
    # Steg 3: Hämta watermarking-metod
    print("  🔍 Hämtar watermarking-metod...", end=" ")
    method = get_watermarking_methods(server, token)
    if not method:
        print("✗ Ingen metod tillgänglig")
        all_results[server] = server_results
        continue
    print(f"✓ Använder metod: {method}")
    server_results["method"] = method
    
    # Steg 4: Skapa versioner för dokument 1-20
    print(f"\n  🎨 Skapar versioner för dokument 1-20:")
    
    created_versions = []
    
    for doc_id in range(1, 21):
        intended_for = f"{USERNAME}_doc{doc_id}"
        print(f"    [ID:{doc_id:2d}] Skapar version...", end=" ")
        
        # Försök skapa version
        success, result = create_watermark(server, token, doc_id, intended_for, method)
        
        if success:
            link = result.get('link')
            version_id = result.get('id')
            print(f"✓ Skapad (link: {link[:12]}...)")
            
            created_versions.append({
                "doc_id": doc_id,
                "version_id": version_id,
                "link": link,
                "intended_for": intended_for
            })
            total_versions_created += 1
        else:
            print(f"✗ {result}")
        
        time.sleep(0.2)
    
    # Steg 5: Ladda ner alla skapade versioner
    if created_versions:
        print(f"\n  📥 Laddar ner {len(created_versions)} versioner:")
        
        for ver in created_versions:
            doc_id = ver['doc_id']
            link = ver['link']
            print(f"    [ID:{doc_id:2d}] Laddar ner...", end=" ")
            
            content = download_version(server, link)
            
            if content:
                # Spara fil
                safe_server = server.replace('.', '_')
                filename = f"server{safe_server}_doc{doc_id}_{ver['intended_for']}.pdf"
                filepath = output_dir / filename
                
                with open(filepath, 'wb') as f:
                    f.write(content)
                
                print(f"✓ Sparad ({len(content)} bytes)")
                
                ver['file'] = filename
                ver['size'] = len(content)
                total_files_downloaded += 1
            else:
                print("✗ Misslyckades")
                ver['file'] = None
            
            time.sleep(0.1)
    
    server_results["versions"] = created_versions
    all_results[server] = server_results
    
    downloaded = len([v for v in created_versions if v.get('file')])
    print(f"\n  📊 Sammanfattning: {len(created_versions)} versioner skapade, {downloaded} nedladdade")

# ============================================================
# SLUTRAPPORT
# ============================================================

print(f"\n{'═'*60}")
print("📋 SLUTRAPPORT")
print(f"{'═'*60}\n")

# Spara resultat
summary_file = output_dir / "created_versions.json"
with open(summary_file, 'w') as f:
    json.dump(all_results, f, indent=2)

print(f"🎯 Totalt antal versioner skapade: {total_versions_created}")
print(f"📥 Totalt antal filer nedladdade: {total_files_downloaded}")
print(f"📁 Filer sparade i: {output_dir}/")
print(f"📄 Sammanfattning: {summary_file}\n")

# Visa detaljerad sammanfattning per server
for server, data in all_results.items():
    versions = data.get('versions', [])
    downloaded = len([v for v in versions if v.get('file')])
    
    if data['login_success']:
        created = len(versions)
        status = '✓' if downloaded == created else '⚠️'
        print(f"{server}: {created} versioner skapade, {downloaded} nedladdade {status}")
    else:
        print(f"{server}: Login misslyckades ✗")

print("\n✓ Klart!\n")

