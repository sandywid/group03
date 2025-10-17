#!/usr/bin/env python3
import argparse, base64, json, os, sys
from secrets import randbits
import requests, pgpy
from rmap.identity_manager import IdentityManager

def load_privkey(path, passphrase):
    key, _ = pgpy.PGPKey.from_file(path)
    if key.is_protected:
        key.unlock(passphrase)
    return key

def decrypt_payload_to_json(payload, my_priv):
    try:
        armored = base64.b64decode(payload).decode("utf-8")
    except Exception:
        armored = payload
    msg = pgpy.PGPMessage.from_blob(armored)
    return json.loads(my_priv.decrypt(msg).message)

def post_auto(url, armored_str):
    # Try Base64 first, fallback to raw ASCII-armored if needed
    b64 = base64.b64encode(armored_str.encode("utf-8")).decode("ascii")
    for data in ({"payload": b64}, {"payload": armored_str}):
        r = requests.post(url, json=data, timeout=20)
        if r.status_code < 400:
            return r.json()
        if "ASCII-armored" not in r.text:
            r.raise_for_status()
    raise Exception("RMAP request failed with 400 both for base64 and raw armor")

def download_to(path, url):
    if not url:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        print(f"✅ PDF sparad till: {path}")
        return True
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser(description="Group_03 RMAP client).")
    ap.add_argument("--target-host", required=True)
    ap.add_argument("--target-port", type=int, default=5000)
    ap.add_argument("--target-group", required=True)
    ap.add_argument("--my-priv", default="keys/server_priv.asc")
    ap.add_argument("--my-pub", default="keys/server_pub.asc")
    ap.add_argument("--passphrase", required=False, default="")
    ap.add_argument("--out", default="downloads/out.pdf")
    args = ap.parse_args()

    identity = "Group_03"

    # Find target group pubkey
    possible_paths = [
        f"keys/servers/{args.target_group}_server_pub.asc",
        f"keys/servers/{args.target_group}.asc",
        f"keys/{args.target_group}_server_pub.asc",
        f"keys/{args.target_group}.asc",
        f"keys/clients/{args.target_group}.asc",
    ]
    target_pub = next((p for p in possible_paths if os.path.exists(p)), None)
    if not target_pub:
        raise FileNotFoundError(f"Hittar ingen publ nyckel för {args.target_group}")
    print(f"🔑 Målserverns pubkey: {target_pub}")

    # Setup IdentityManager using our pub+priv keys
    im = IdentityManager("keys/clients", target_pub, args.my_priv, args.passphrase)
    my_priv = load_privkey(args.my_priv, args.passphrase)

    base = f"http://{args.target_host}:{args.target_port}"
    print(f"🌐 Kontaktar {args.target_group} på {base}")

    # Message 1
    nonce_client = randbits(64)
    msg1_plain = {"nonceClient": nonce_client, "identity": identity}
    armored1 = im.encrypt_for_server(msg1_plain)
    r1_json = post_auto(f"{base}/rmap-initiate", armored1)

    resp1_plain = decrypt_payload_to_json(r1_json["payload"], my_priv)
    nonce_server = int(resp1_plain["nonceServer"])
    print(f"📩 Mottog nonceServer={nonce_server}")

    # Message 2
    msg2_plain = {"nonceServer": nonce_server}
    armored2 = im.encrypt_for_server(msg2_plain)
    r2_json = post_auto(f"{base}/rmap-get-link", armored2)
    result = r2_json.get("result") or r2_json.get("link")

    if download_to(args.out, result):
        return
    fallback = f"{base}/api/get-version/{result}"
    if download_to(args.out, fallback):
        return
    print("ℹ️ Ingen PDF hämtades – resultatet var varken URL eller fungerande kod.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)
