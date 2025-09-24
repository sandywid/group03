import os, base64, json, secrets, time, hashlib
from flask import Blueprint, request, jsonify
import gnupg

bp = Blueprint("rmap", __name__)

# Configure paths
GPG_HOME = r" C:\Users\fatin\Documents\group03\server\gpghome"
CLIENT_KEYS_DIR = r" C:\Users\fatin\Documents\group03\server\keys\public-keys"
gpg = gnupg.GPG(gnupghome=GPG_HOME)

_sessions = {}  # store temporary sessions

# Helper: decrypt incoming payload
def decrypt_payload(payload_b64):
    armored = base64.b64decode(payload_b64).decode()
    dec = gpg.decrypt(armored)
    if not dec.ok:
        raise Exception("Decrypt failed")
    return json.loads(str(dec))

# Helper: encrypt response to a group
def encrypt_payload(obj, identity):
    plaintext = json.dumps(obj)
    enc = gpg.encrypt(plaintext, identity, always_trust=True, armor=True)
    if not enc.ok:
        raise Exception("Encrypt failed")
    return base64.b64encode(str(enc).encode()).decode()

@bp.route("/rmap-initiate", methods=["POST"])
def rmap_initiate():
    msg = decrypt_payload(request.json["payload"])
    nonce_client = int(msg["nonceClient"])
    identity = msg["identity"]

    nonce_server = secrets.randbits(64)
    _sessions[str(nonce_server)] = {
        "identity": identity,
        "nonceClient": nonce_client,
        "expires": time.time() + 300,
    }

    resp = {"nonceClient": nonce_client, "nonceServer": nonce_server}
    return jsonify({"payload": encrypt_payload(resp, identity)})

@bp.route("/rmap-get-link", methods=["POST"])
def rmap_get_link():
    msg = decrypt_payload(request.json["payload"])
    nonce_server = str(msg["nonceServer"])
    sess = _sessions.get(nonce_server)
    if not sess or time.time() > sess["expires"]:
        return jsonify({"error": "session expired"}), 400

    # create link = hash of nonces
    concat = f"{sess['nonceClient']}{nonce_server}".encode()
    link = hashlib.sha256(concat).hexdigest()[:32]

    return jsonify({"result": link})
