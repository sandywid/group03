import os
import io
import hashlib
import secrets
import re
from pathlib import Path
import datetime as dt
from pathlib import Path
from functools import wraps

import base64 #added for end of pahse /Sandra
import binascii #added for end of pahse /Sandra

from flask import Flask, jsonify, request, g, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

#added for loggning /Sandra
from flag_detection import detect_flag_attempt
import logging, sys, json
try:
    from pythonjsonlogger import jsonlogger
    formatter = jsonlogger.JsonFormatter()
except Exception:
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')

log_path = os.getenv("LOG_PATH", "/var/log/app/app.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# --- 1. Log to stdout (can be seen in docker logs) /Sandra
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)

# --- 2. Log to file (can be seen in group03/logs/app.log) /Sandra
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Testlog when starting /Sandra
logging.getLogger(__name__).info({"event": "startup", "message": "Logger initialized", "log_path": log_path})

#added this to include rate limiting, to prevent eg. brute-force attacks /Sandra
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

#added this for end of phase update/Sandra 
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, url_for
from werkzeug.exceptions import BadRequest
import json
import tempfile
import subprocess
from flask import current_app
from sqlalchemy import text, create_engine
from datetime import datetime

# end of phase one / Sandra
def _db_url_from_cfg(cfg) -> str:
    return (
        f"mysql+pymysql://{cfg['DB_USER']}:{cfg['DB_PASSWORD']}"
        f"@{cfg['DB_HOST']}:{cfg['DB_PORT']}/{cfg['DB_NAME']}?charset=utf8mb4"
    )

# end of phase one / Sandra
def get_engine():
    app = current_app  # using the active Flask-app /Sandra
    eng = app.config.get("_ENGINE")
    if eng is None:
        eng = create_engine(_db_url_from_cfg(app.config), pool_pre_ping=True, future=True)
        app.config["_ENGINE"] = eng
    return eng

# end of phase one / Sandra
from rmap.identity_manager import IdentityManager
from rmap.rmap import RMAP

import pickle as _std_pickle
try:
    import dill as _pickle  # allows loading classes not importable by module path
except Exception:  # dill is optional
    _pickle = _std_pickle

rmap = None # /Sandra

import watermarking_utils as WMUtils
from watermarking_method import WatermarkingMethod
#from watermarking_utils import METHODS, apply_watermark, read_watermark, explore_pdf, is_watermarking_applicable, get_method

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Keys for end of phase one/Sandra
KEYS_DIR = os.path.join(BASE_DIR, "keys")
CLIENT_KEYS_DIR = os.path.join(KEYS_DIR, "clients")
SERVER_PUB = os.path.join(KEYS_DIR, "server_pub.asc")
SERVER_PRIV = os.path.join(KEYS_DIR, "server_priv.asc")


# Fils/PDF /Sandra
STATIC_DIR = Path(BASE_DIR) / "static"
BASE_PDF = STATIC_DIR / "Group_3.pdf"  


def init_rmap():
    """Initiera RMAP with right key paths."""
    id_manager = IdentityManager(
        CLIENT_KEYS_DIR,  # clients public keys (clients/*.asc) /Sandra 
        SERVER_PUB,       # serverns public keys /Sandra
        SERVER_PRIV,       # serverns private key /Sandra
    )
    return RMAP(id_manager)


def _ensure_dirs():
    (Path(current_app.config["STORAGE_DIR"]) / "versions").mkdir(parents=True, exist_ok=True)

def _watermark_and_save(secret: str) -> str:
    """
    Skapar vattenmärkt PDF av BASE_PDF med 'secret' som stämpeltext.
    Sparas som static/versions/<secret>.pdf
    Returnerar absolut sökväg till den vattenmärkta filen.
    """
    _ensure_dirs()
    if not BASE_PDF.exists():
        raise BadRequest(f"Saknar original-PDF: {BASE_PDF}")

    out_path = VERSIONS_DIR / f"{secret}.pdf"
    # PDFish & Chips — stämpla hemligheten i PDF:en
    add_stamp(str(BASE_PDF), str(out_path), str(secret))

    # Fallback om något gick fel
    if not out_path.exists() or out_path.stat().st_size == 0:
        shutil.copyfile(BASE_PDF, out_path)

    return str(out_path)

#added for end of phase oen update so that they will get a DocumentID / Sandra

def _file_sha256_hex(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _ensure_document_for_path(path_str: str, owner_id: int = 1) -> int:
    p = Path(path_str)
    
    with get_engine().begin() as conn:
        row = conn.execute(text("""
            SELECT id FROM Documents WHERE path = :path LIMIT 1
        """), {"path": str(p)}).first()
        if row:
            return int(row.id)

    # Saknas filen på disk? ge tydligt fel
    if not p.is_file():
        raise FileNotFoundError(f"Source PDF not found: {p.resolve()}")
      
    sha_hex = _file_sha256_hex(p)
    size = p.stat().st_size

    with get_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO Documents (name, path, ownerid, sha256, size)
            VALUES (:name, :path, :ownerid, UNHEX(:sha256hex), :size)
        """), {
            "name": p.name,
            "path": str(p),
            "ownerid": owner_id,
            "sha256hex": sha_hex,
            "size": int(size),
        })
        new_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        return int(new_id)

def create_app():
    app = Flask(__name__)
    #added for end of phase one /Sandra
    global rmap
    if rmap is None:
        rmap = init_rmap()

#Added for logs /Sandra 
    # enkel JSON-logger till stdout (docker log driver fångar detta)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(jsonlogger.JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    
    # se även till att logger "app.flag_detector" använder root
    @app.before_request
    def before():
        detect_flag_attempt()

    @app.after_request
    def after(response):
        # Om flag_attempt: vi kan välja blockera tidigt eller låta request gå vidare men logga
        if getattr(g, "flag_attempt", False):
            # ex: sätt header så att klient får generisk 403 (valfritt)
            response.status_code = 403
            response.set_data("Don't steal our flag man")
            # Optionellt: skriv en extra loggrad med respons
            logging.getLogger("app.flag_detector").warning({
                "event": "flag_attempt_blocked",
                "request_id": g.request_id,
                "client_ip": g.flag_attempt_event["client_ip"]
            })
        return response


#added this to prevent eg. brute-force - baseline for the whole app/Sandra
    limiter = Limiter(
        key_func=get_remote_address,  # per-IP as standard
        app=app,
        default_limits=["200 per day", "50 per hour"]  # baseline for all endpoints
    )

    # key function: per log-in, if not logged-in its per IP/Sandra
    def user_or_ip():
        try:
            return f"user:{int(g.user['id'])}"
        except Exception:
            return f"ip:{get_remote_address()}"

    #key for each account at log-in (fallback to IP)/Sandra
    def login_key():
        body = request.get_json(silent=True) or {}
        login = (body.get("login") or body.get("email") or "").strip().lower()
        return f"acct:{login}" if login else f"ip:{get_remote_address()}"


    #shared limit for upload (per user/IP)/Sandra
    upload_limit = limiter.shared_limit(
        "2 per minute; 20 per hour",
        scope="upload",
        key_func=user_or_ip
    )



    # --- Config ---
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "changed-it-a-little-in-case-of-that-the-env-does-not-work") #changed hahah/Sandra
    app.config["STORAGE_DIR"] = Path(os.environ.get("STORAGE_DIR", "./storage")).resolve()
    app.config["TOKEN_TTL_SECONDS"] = int(os.environ.get("TOKEN_TTL_SECONDS", "86400"))

    app.config["DB_USER"] = os.environ.get("DB_USER", "tatou")
    app.config["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "tatou")
    app.config["DB_HOST"] = os.environ.get("DB_HOST", "db")
    app.config["DB_PORT"] = int(os.environ.get("DB_PORT", "3306"))
    app.config["DB_NAME"] = os.environ.get("DB_NAME", "tatou")

    app.config["STORAGE_DIR"].mkdir(parents=True, exist_ok=True)

    # --- DB engine only (no Table metadata) ---
    def db_url() -> str:
        return (
            f"mysql+pymysql://{app.config['DB_USER']}:{app.config['DB_PASSWORD']}"
            f"@{app.config['DB_HOST']}:{app.config['DB_PORT']}/{app.config['DB_NAME']}?charset=utf8mb4"
        )

    def get_engine():
        eng = app.config.get("_ENGINE")
        if eng is None:
            eng = create_engine(db_url(), pool_pre_ping=True, future=True)
            app.config["_ENGINE"] = eng
        return eng

    # --- Helpers ---
    def _serializer():
        return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth")

    def _auth_error(msg: str, code: int = 401):
        return jsonify({"error": msg}), code

    def require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return _auth_error("Missing or invalid Authorization header")
            token = auth.split(" ", 1)[1].strip()
            try:
                data = _serializer().loads(token, max_age=app.config["TOKEN_TTL_SECONDS"])
            except SignatureExpired:
                return _auth_error("Token expired")
            except BadSignature:
                return _auth_error("Invalid token")
            g.user = {"id": int(data["uid"]), "login": data["login"], "email": data.get("email")}
            return f(*args, **kwargs)
        return wrapper

    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    # --- Routes ---
    
    @app.route("/<path:filename>")
    def static_files(filename):
        return app.send_static_file(filename)

    @app.route("/")
    def home():
        return app.send_static_file("index.html")
    
    @app.get("/healthz")
    @limiter.exempt #added this, no restrictions 
    def healthz():
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"message": "The server is up and running.", "db_connected": db_ok}), 200

    # POST /api/create-user {username,email, login, password}
    @app.post("/api/create-user")
    def create_user():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip().lower()
        login = (payload.get("login") or "").strip()
        password = payload.get("password") or ""
    
    # Input validation
        if not email or not login or not password:
            return jsonify({"error": "email, login, and password are required"}), 400
    
    # Add username format validation
        if not re.match(r'^[a-zA-Z0-9_-]{3,64}$', login):
            return jsonify({
            "error": "Username must be 3-64 characters long and contain only letters, numbers, hyphens, and underscores"
        }), 400

        hpw = generate_password_hash(password)

        try:
            with get_engine().begin() as conn:
            # Check if username or email already exists for better error messages
                existing = conn.execute(
                    text("SELECT login, email FROM Users WHERE login = :login OR email = :email"),
                    {"login": login, "email": email}
            ).first()
            
                if existing:
                    if existing.login == login:
                        return jsonify({"error": "Username already taken"}), 409
                    if existing.email == email:
                        return jsonify({"error": "Email already registered"}), 409
            
            # Insert the new user
                res = conn.execute(
                    text("INSERT INTO Users (email, hpassword, login) VALUES (:email, :hpw, :login)"),
                    {"email": email, "hpw": hpw, "login": login},
            )
                uid = int(res.lastrowid)
                row = conn.execute(
                    text("SELECT id, email, login FROM Users WHERE id = :id"),
                {"id": uid},
            ).one()
        except IntegrityError as e:
        # More specific error messages
            error_str = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
            if 'uq_users_login' in error_str or 'login' in error_str:
                return jsonify({"error": "Username already taken"}), 409
            elif 'uq_users_email' in error_str or 'email' in error_str:
                return jsonify({"error": "Email already registered"}), 409
            else:
                return jsonify({"error": "Account could not be created (duplicate data)"}), 409
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        return jsonify({"id": row.id, "email": row.email, "login": row.login}), 201

    # POST /api/login {login, password}
    @app.post("/api/login")
    @limiter.limit("3 per minute; 10 per hour", key_func=login_key)   # added per konto
    @limiter.limit("20 per minute", key_func=get_remote_address)      # added per IP
    def login():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""
        if not email or not password:
            return jsonify({"error": "email and password are required"}), 400

        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT id, email, login, hpassword FROM Users WHERE email = :email LIMIT 1"),
                    {"email": email},
                ).first()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        if not row or not check_password_hash(row.hpassword, password):
            return jsonify({"error": "invalid credentials"}), 401

        token = _serializer().dumps({"uid": int(row.id), "login": row.login, "email": row.email})
        return jsonify({"token": token, "token_type": "bearer", "expires_in": app.config["TOKEN_TTL_SECONDS"]}), 200

    # POST /api/upload-document  (multipart/form-data)
    @app.post("/api/upload-document")
    @require_auth
    @upload_limit #added this for brute-force 
    def upload_document():
        if "file" not in request.files:
            return jsonify({"error": "file is required (multipart/form-data)"}), 400
        file = request.files["file"]

# --- PDF check ---      
        if not file or file.filename == "": 
            return jsonify({"error": "empty filename"}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "only PDF files are allowed (wrong extension)"}), 400
        if file.mimetype != "application/pdf":
            return jsonify({"error": "only PDF files are allowed (wrong mimetype)"}), 400

    # Read a few bytes to verify the PDF signature
        head = file.read(5)
        file.seek(0) # Seek back so the entire file can be saved later
        if head != b"%PDF-":
            return jsonify({"error": "file is not a valid PDF"}), 400


        fname = file.filename

        user_dir = app.config["STORAGE_DIR"] / "files" / g.user["login"]
        user_dir.mkdir(parents=True, exist_ok=True)

        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        final_name = (request.form.get("name") or Path(fname).stem).strip()
        if not re.fullmatch(r"[A-Za-zÅÄÖåäö0-9.]+", final_name):
            return jsonify({
                "error": "The name can only contain letters (A–Z, a–z, ÅÄÖ, åäö) – and numbers (0-9) - no special characters exept for dot."
            }), 400
        stored_name = f"{ts}__{fname}"
        stored_path = user_dir / stored_name
        file.save(stored_path)

        sha_hex = _sha256_file(stored_path)
        size = stored_path.stat().st_size

        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO Documents (name, path, ownerid, sha256, size)
                        VALUES (:name, :path, :ownerid, UNHEX(:sha256hex), :size)
                    """),
                    {
                        "name": final_name,
                        "path": str(stored_path),
                        "ownerid": int(g.user["id"]),
                        "sha256hex": sha_hex,
                        "size": int(size),
                    },
                )
                did = int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar())
                row = conn.execute(
                    text("""
                        SELECT id, name, creation, HEX(sha256) AS sha256_hex, size
                        FROM Documents
                        WHERE id = :id
                    """),
                    {"id": did},
                ).one()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        return jsonify({
            "id": int(row.id),
            "name": row.name,
            "creation": row.creation.isoformat() if hasattr(row.creation, "isoformat") else str(row.creation),
            "sha256": row.sha256_hex,
            "size": int(row.size),
        }), 201

    # GET /api/list-documents
    @app.get("/api/list-documents")
    @require_auth
    def list_documents():
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT id, name, creation, HEX(sha256) AS sha256_hex, size
                        FROM Documents
                        WHERE ownerid = :uid
                        ORDER BY creation DESC
                    """),
                    {"uid": int(g.user["id"])},
                ).all()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        docs = [{
            "id": int(r.id),
            "name": r.name,
            "creation": r.creation.isoformat() if hasattr(r.creation, "isoformat") else str(r.creation),
            "sha256": r.sha256_hex,
            "size": int(r.size),
        } for r in rows]
        return jsonify({"documents": docs}), 200



    # GET /api/list-versions
    @app.get("/api/list-versions")
    @app.get("/api/list-versions/<int:document_id>")
    @require_auth
    def list_versions(document_id: int | None = None):
        # Support both path param and ?id=/ ?documentid=
        if document_id is None:
            document_id = request.args.get("id") or request.args.get("documentid")
            try:
                document_id = int(document_id)
            except (TypeError, ValueError):
                return jsonify({"error": "document id required"}), 400
       
        #took away secret /S

        try:
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT v.id, v.documentid, v.link, v.intended_for, v.method
                        FROM Users u
                        JOIN Documents d ON d.ownerid = u.id
                        JOIN Versions v ON d.id = v.documentid
                        WHERE u.login = :glogin AND d.id = :did
                    """),
                    {"glogin": str(g.user["login"]), "did": document_id},
                ).all()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        versions = [{
            "id": int(r.id),
            "documentid": int(r.documentid),
            "link": r.link,
            "intended_for": r.intended_for,
            "method": r.method,
            #took away secret / S
        } for r in rows]
        return jsonify({"versions": versions}), 200
    
    
    # GET /api/list-all-versions
    @app.get("/api/list-all-versions")
    @require_auth
    def list_all_versions():
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT v.id, v.documentid, v.link, v.intended_for, v.method
                        FROM Users u
                        JOIN Documents d ON d.ownerid = u.id
                        JOIN Versions v ON d.id = v.documentid
                        WHERE u.login = :glogin
                    """),
                    {"glogin": str(g.user["login"])},
                ).all()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        versions = [{
            "id": int(r.id),
            "documentid": int(r.documentid),
            "link": r.link,
            "intended_for": r.intended_for,
            "method": r.method,
        } for r in rows]
        return jsonify({"versions": versions}), 200
    
    # GET /api/get-document or /api/get-document/<id>  → returns the PDF (inline)
    @app.get("/api/get-document")
    @app.get("/api/get-document/<int:document_id>")
    @require_auth
    def get_document(document_id: int | None = None):
    
        # Support both path param and ?id=/ ?documentid=
        if document_id is None:
            document_id = request.args.get("id") or request.args.get("documentid")
            try:
                document_id = int(document_id)
            except (TypeError, ValueError):
                return jsonify({"error": "document id required"}), 400
        
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT id, name, path, HEX(sha256) AS sha256_hex, size
                        FROM Documents
                        WHERE id = :id AND ownerid = :uid
                        LIMIT 1
                    """),
                    {"id": document_id, "uid": int(g.user["id"])},
                ).first()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        # Don’t leak whether a doc exists for another user
        if not row:
            return jsonify({"error": "document not found"}), 404

        file_path = Path(row.path)

        # Basic safety: ensure path is inside STORAGE_DIR and exists
        try:
            file_path.resolve().relative_to(app.config["STORAGE_DIR"].resolve())
        except Exception:
            # Path looks suspicious or outside storage
            return jsonify({"error": "document path invalid"}), 500

        if not file_path.exists():
            return jsonify({"error": "file missing on disk"}), 410

        # Serve inline with caching hints + ETag based on stored sha256
        resp = send_file(
            file_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=row.name if row.name.lower().endswith(".pdf") else f"{row.name}.pdf",
            conditional=True,   # enables 304 if If-Modified-Since/Range handling
            max_age=0,
            last_modified=file_path.stat().st_mtime,
        )
        # Strong validator
        if isinstance(row.sha256_hex, str) and row.sha256_hex:
            resp.set_etag(row.sha256_hex.lower())

        resp.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return resp
    
    # GET /api/get-version/<link>  → returns the watermarked PDF (inline)
    @app.get("/api/get-version/<link>")
    def get_version_api(link: str):
        link_in = link  # behåll EXAKT sträng från webben

        # 1) Försök exakt match i DB
        with get_engine().begin() as conn:
            path_str = conn.execute(
                text("SELECT path FROM Versions WHERE link = :link LIMIT 1"),
                {"link": link_in},
            ).scalar_one_or_none()

            # 2) Fallback: om det ser ut som 32-hex, testa lowercase (bakåtkomp.)
            if path_str is None and re.fullmatch(r"[0-9A-Fa-f]{32}", link_in):
                path_str = conn.execute(
                    text("SELECT path FROM Versions WHERE link = :link LIMIT 1"),
                    {"link": link_in.lower()},
                ).scalar_one_or_none()

        if path_str is None:
            return jsonify({"error": "not found"}), 404

        p = Path(path_str)
        if not p.is_file():
            return jsonify({"error": "file missing"}), 410

        resp = send_file(
            p,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=p.name,
        )
        resp.headers["Cache-Control"] = "private, no-store"
        return resp

    
    # Helper: resolve path safely under STORAGE_DIR (handles absolute/relative)
    def _safe_resolve_under_storage(p: str, storage_root: Path) -> Path:
        storage_root = storage_root.resolve()
        fp = Path(p)
        if not fp.is_absolute():
            fp = storage_root / fp
        fp = fp.resolve()
        # Python 3.12 has is_relative_to on Path
        if hasattr(fp, "is_relative_to"):
            if not fp.is_relative_to(storage_root):
                raise RuntimeError(f"path {fp} escapes storage root {storage_root}")
        else:
            try:
                fp.relative_to(storage_root)
            except ValueError:
                raise RuntimeError(f"path {fp} escapes storage root {storage_root}")
        return fp

    # DELETE /api/delete-document  (and variants)
    @app.route("/api/delete-document", methods=["DELETE", "POST"])  # POST supported for convenience
    @app.route("/api/delete-document/<document_id>", methods=["DELETE"])
    @require_auth
    def delete_document(document_id: int | None = None):
        # accept id from path, query (?id= / ?documentid=), or JSON body on POST
        if not document_id:
            document_id = (
                request.args.get("id")
                or request.args.get("documentid")
                or (request.is_json and (request.get_json(silent=True) or {}).get("id"))
            )
        try:
            doc_id = document_id
        except (TypeError, ValueError):
            return jsonify({"error": "document id required"}), 400

        # Fetch the document (enforce ownership)
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM Documents WHERE id = :id AND ownerid = :uid"), 
                    {"id": doc_id, "uid": int(g.user["id"])}
                ).first()
        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        if not row:
            # Don’t reveal others’ docs—just say not found
            return jsonify({"error": "document not found"}), 404

        # Resolve and delete file (best effort)
        storage_root = Path(app.config["STORAGE_DIR"])
        file_deleted = False
        file_missing = False
        delete_error = None
        try:
            fp = _safe_resolve_under_storage(row.path, storage_root)
            if fp.exists():
                try:
                    fp.unlink()
                    file_deleted = True
                except Exception as e:
                    delete_error = f"failed to delete file: {e}"
                    app.logger.warning("Failed to delete file %s for doc id=%s: %s", fp, row.id, e)
            else:
                file_missing = True
        except RuntimeError as e:
            # Path escapes storage root; refuse to touch the file
            delete_error = str(e)
            app.logger.error("Path safety check failed for doc id=%s: %s", row.id, e)

        # Delete DB row (will cascade to Version if FK has ON DELETE CASCADE)
        try:
            with get_engine().begin() as conn:
                conn.execute(text("DELETE FROM Documents WHERE id = :id"), {"id": doc_id})
        except Exception as e:
            return jsonify({"error": f"database error during delete: {str(e)}"}), 503

        return jsonify({
            "deleted": True,
            "id": doc_id,
            "file_deleted": file_deleted,
            "file_missing": file_missing,
            "note": delete_error,   # null/omitted if everything was fine
        }), 200
        
        
    # POST /api/create-watermark or /api/create-watermark/<id>  → create watermarked pdf and returns metadata
    @app.post("/api/create-watermark")
    @app.post("/api/create-watermark/<int:document_id>")
    @require_auth
    def create_watermark(document_id: int | None = None):
        # accept id from path, query (?id= / ?documentid=), or JSON body on GET
        if not document_id:
            document_id = (
                request.args.get("id")
                or request.args.get("documentid")
                or (request.is_json and (request.get_json(silent=True) or {}).get("id"))
            )
        try:
            doc_id = document_id
        except (TypeError, ValueError):
            return jsonify({"error": "document id required"}), 400
            
        payload = request.get_json(silent=True) or {}
        # allow a couple of aliases for convenience /Sandra
        method = payload.get("method")
        intended_for = payload.get("intended_for")
        position = payload.get("position") or None
        secret = payload.get("secret")
        key = payload.get("key")

        # validate input
        try:
            doc_id = int(doc_id)
        except (TypeError, ValueError):
            return jsonify({"error": "document_id (int) is required"}), 400
        if not method or not intended_for or not isinstance(secret, str) or not isinstance(key, str):
            return jsonify({"error": "method, intended_for, secret, and key are required"}), 400

        # lookup the document; enforced ownership /Sandra
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT id, name, path
                        FROM Documents
                        WHERE id = :id AND ownerid = :uid
                        LIMIT 1
                    """),
                    {"id": doc_id, "uid": int(g.user["id"])}
                ).first()

        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

        if not row:
            return jsonify({"error": "document not found"}), 404

        # resolve path safely under STORAGE_DIR
        storage_root = Path(app.config["STORAGE_DIR"]).resolve()
        file_path = Path(row.path)
        if not file_path.is_absolute():
            file_path = storage_root / file_path
        file_path = file_path.resolve()
        try:
            file_path.relative_to(storage_root)
        except ValueError:
            return jsonify({"error": "document path invalid"}), 500
        if not file_path.exists():
            return jsonify({"error": "file missing on disk"}), 410

        # check watermark applicability
        try:
            applicable = WMUtils.is_watermarking_applicable(
                method=method,
                pdf=str(file_path),
                position=position
            )
            if applicable is False:
                return jsonify({"error": "watermarking method not applicable"}), 400
        except Exception as e:
            return jsonify({"error": f"watermark applicability check failed: {e}"}), 400

        # apply watermark → bytes
        try:
            wm_bytes: bytes = WMUtils.apply_watermark(
                pdf=str(file_path),
                secret=secret,
                key=key,
                method=method,
                position=position
            )
            if not isinstance(wm_bytes, (bytes, bytearray)) or len(wm_bytes) == 0:
                return jsonify({"error": "watermarking produced no output"}), 500
        except Exception as e:
            return jsonify({"error": f"watermarking failed: {e}"}), 500

        # build destination file name: "<original_name>__<intended_to>.pdf"
        base_name = Path(row.name or file_path.name).stem
        intended_slug = secure_filename(intended_for)
        dest_dir = file_path.parent / "watermarks"
        dest_dir.mkdir(parents=True, exist_ok=True)

        candidate = f"{base_name}__{intended_slug}.pdf"
        dest_path = dest_dir / candidate

        # write bytes
        try:
            with dest_path.open("wb") as f:
                f.write(wm_bytes)
        except Exception as e:
            return jsonify({"error": f"failed to write watermarked file: {e}"}), 500

        # link token = random hash instead of SHA1 / Sandra 
        link_token = secrets.token_urlsafe(24)

        try:
            with get_engine().begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO Versions (documentid, link, intended_for, secret, method, position, path)
                        VALUES (:documentid, :link, :intended_for, :secret, :method, :position, :path)
                    """),
                    {
                        "documentid": doc_id,
                        "link": link_token,
                        "intended_for": intended_for,
                        "secret": secret,
                        "method": method,
                        "position": position or "",
                        "path": dest_path
                    },
                )
                vid = int(conn.execute(text("SELECT LAST_INSERT_ID()")).scalar())
        except Exception as e:
            # best-effort cleanup if DB insert fails
            try:
                dest_path.unlink(missing_ok=True)
            except Exception:
                pass
            return jsonify({"error": f"database error during version insert: {e}"}), 503

        return jsonify({
            "id": vid,
            "documentid": doc_id,
            "link": link_token,
            "intended_for": intended_for,
            "method": method,
            "position": position,
            "filename": candidate,
            "size": len(wm_bytes),
        }), 201
        
        
    @app.post("/api/load-plugin")
    @require_auth
    def load_plugin():
        """
        Load a serialized Python class implementing WatermarkingMethod from
        STORAGE_DIR/files/plugins/<filename>.{pkl|dill} and register it in wm_mod.METHODS.
        Body: { "filename": "MyMethod.pkl", "overwrite": false }
        """
        payload = request.get_json(silent=True) or {}
        filename = (payload.get("filename") or "").strip()
        overwrite = bool(payload.get("overwrite", False))

        if not filename:
            return jsonify({"error": "filename is required"}), 400

        # Locate the plugin in /storage/files/plugins (relative to STORAGE_DIR)
        storage_root = Path(app.config["STORAGE_DIR"])
        plugins_dir = storage_root / "files" / "plugins"
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            plugin_path = plugins_dir / filename
        except Exception as e:
            return jsonify({"error": f"plugin path error: {e}"}), 500

        if not plugin_path.exists():
            return jsonify({"error": f"plugin file not found: {safe}"}), 404

        # Unpickle the object (dill if available; else std pickle)
        try:
            with plugin_path.open("rb") as f:
                obj = _pickle.load(f)
        except Exception as e:
            return jsonify({"error": f"failed to deserialize plugin: {e}"}), 400

        # Accept: class object, or instance (we'll promote instance to its class)
        if isinstance(obj, type):
            cls = obj
        else:
            cls = obj.__class__

        # Determine method name for registry
        method_name = getattr(cls, "name", getattr(cls, "__name__", None))
        if not method_name or not isinstance(method_name, str):
            return jsonify({"error": "plugin class must define a readable name (class.__name__ or .name)"}), 400

        # Validate interface: either subclass of WatermarkingMethod or duck-typing
        has_api = all(hasattr(cls, attr) for attr in ("add_watermark", "read_secret"))
        if WatermarkingMethod is not None:
            is_ok = issubclass(cls, WatermarkingMethod) and has_api
        else:
            is_ok = has_api
        if not is_ok:
            return jsonify({"error": "plugin does not implement WatermarkingMethod API (add_watermark/read_secret)"}), 400
            
        # Register the class (not an instance) /Sandra
        WMUtils.METHODS[method_name] = cls()
        
        return jsonify({
            "loaded": True,
            "filename": filename,
            "registered_as": method_name,
            "class_qualname": f"{getattr(cls, '__module__', '?')}.{getattr(cls, '__qualname__', cls.__name__)}",
            "methods_count": len(WMUtils.METHODS)
        }), 201
        
    
    
    # GET /api/get-watermarking-methods -> {"methods":[{"name":..., "description":...}, ...], "count":N}
    @app.get("/api/get-watermarking-methods")
    def get_watermarking_methods():
        methods = []

        for m in WMUtils.METHODS:
            methods.append({"name": m, "description": WMUtils.get_method(m).get_usage()})
            
        return jsonify({"methods": methods, "count": len(methods)}), 200
            
    # POST /api/read-watermark
    @app.post("/api/read-watermark")
    @app.post("/api/read-watermark/<int:document_id>")
    @require_auth
    def read_watermark(document_id: int | None = None):
    # Get document-ID from path, query (?id=/ ?documentid=) or body /Sandra
        if not document_id:
            document_id = (
                request.args.get("id")
                or request.args.get("documentid")
                or (request.is_json and (request.get_json(silent=True) or {}).get("id"))
            )
        try:
            doc_id = int(document_id)
        except (TypeError, ValueError):
            return jsonify({"error": "document id required"}), 400

        payload = request.get_json(silent=True) or {}
        method   = payload.get("method")
        key      = payload.get("key")
        position = payload.get("position") or None
        link     = payload.get("link") # NEW: Support to read through the link/Sandra
        version_id = payload.get("version_id") or payload.get("versionId")  #so they only need a key/Sandra

    # CHANGED /Sandra
        if not isinstance(key, str):
            return jsonify({"error": "key is required"}), 400 #Added/Sandnra

        storage_root = Path(app.config["STORAGE_DIR"]).resolve()  # MOVED/Sandrsa

#I changed this so they only need the key and not method /Sandra
        try:
            with get_engine().connect() as conn:
                file_row = None

                if version_id:  
                    vrow = conn.execute(
                        text("""
                            SELECT v.path, v.method, v.link
                            FROM Versions v
                            JOIN Documents d ON d.id = v.documentid
                            WHERE v.id = :vid
                            AND d.id = :did
                            AND d.ownerid = :uid
                            LIMIT 1
                        """),
                        {"vid": int(version_id), "did": doc_id, "uid": int(g.user["id"])},
                    ).first()
                    if not vrow:
                        return jsonify({"error": "version not found"}), 404
                    file_path = Path(vrow.path)
                    method = vrow.method or method   
                    link   = vrow.link or link       

                elif link:  # old code here /Sandra
                    file_row = conn.execute(
                        text("""
                            SELECT v.path
                            FROM Versions v
                            JOIN Documents d ON d.id = v.documentid
                            WHERE v.link = :link
                            AND d.id = :did
                            AND d.ownerid = :uid
                            LIMIT 1
                        """),
                        {"link": str(link), "did": doc_id, "uid": int(g.user["id"])},
                    ).first()
                    if not file_row:
                        return jsonify({"error": "version not found"}), 404
                    file_path = Path(file_row.path)

                else:  # Fallback: originalfile /Sandra
                    doc_row = conn.execute(
                        text("""
                            SELECT path
                            FROM Documents
                            WHERE id = :did AND ownerid = :uid
                            LIMIT 1
                        """),
                        {"did": doc_id, "uid": int(g.user["id"])},
                    ).first()
                    if not doc_row:
                        return jsonify({"error": "document not found"}), 404
                    file_path = Path(doc_row.path)

        except Exception as e:
            return jsonify({"error": f"database error: {str(e)}"}), 503

    # Path resolution and file checks (unchanged) /Sandra
        if not file_path.is_absolute():
            file_path = (storage_root / file_path).resolve()
        else:
            file_path = file_path.resolve()
        try:
            file_path.relative_to(storage_root)
        except ValueError:
            return jsonify({"error": "document path invalid"}), 500
        if not file_path.exists():
            return jsonify({"error": "file missing on disk"}), 410

        try:
    # Try with position if supported /Sandra
            try:
                result = WMUtils.read_watermark(method=method, pdf=str(file_path), key=key, position=position)
            except TypeError:
        # The method does not accept 'position' —> proceeding without it/Sandra
                result = WMUtils.read_watermark(method=method, pdf=str(file_path), key=key)

            if isinstance(result, tuple) and len(result) == 2:
                ok, secret = result
                if not ok:
                    return jsonify({"found": False}), 404
            else:
                secret = result
                if secret in (None, "", False):
                    return jsonify({"found": False}), 404

            return jsonify({
                "documentid": doc_id,
                "method": method,
                "position": position,
                "secret": secret
            }), 200  # CHANGED: retur 200 OK instead of 201 Created /Sandra

        except Exception as e:
            return jsonify({"error": f"Error when attempting to read watermark: {e}"}), 400

#added this for end of phase one/Sandra

    def _version_output_path(document_id: int, link_hex: str) -> Path:
        root = Path(current_app.config["STORAGE_DIR"]) / "versions"
        now = datetime.utcnow()
        return (root / f"{now:%Y}" / f"{now:%m}" / str(document_id) / f"{link_hex}.pdf")

    def _create_rmap_watermarked_pdf(link_secret: str, identity: str | None = None) -> str:
        if not BASE_PDF.exists():
            raise RuntimeError(f"Missing original PDF: {BASE_PDF}")

        doc_id = _ensure_document_for_path(str(BASE_PDF), owner_id=1)
        out_path = _version_output_path(doc_id, link_secret)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # --- försök bästa metod ---
        try:
            from PDFishAndChipsStamp import PDFishAndChipsStamp
            wm = PDFishAndChipsStamp()
            secret_payload = (identity.strip() if isinstance(identity, str) and identity.strip() else str(link_secret))
            watermarked_bytes = wm.add_watermark(
                pdf=str(BASE_PDF),
                secret=secret_payload,
                key="rmap_session_key_2025", #I know it should not be here but i got too angry cause it dit not work to move it :) /Sandra
                position=None,
            )


            out_path.write_bytes(watermarked_bytes)
            return str(out_path)
        except Exception:
            pass

        # --- fallback 1 ---
        try:
            from add_stamp import add_stamp
            watermarked_bytes = add_stamp(
                pdf=str(BASE_PDF),
                secret=str(link_secret),
                position=None,
            )
            out_path.write_bytes(watermarked_bytes)
            return str(out_path)
        except Exception:
            pass

        # --- sista fallback: kopiera originalet ---
        out_path.write_bytes(Path(BASE_PDF).read_bytes())
        return str(out_path)


    def _store_rmap_version(link_hex: str, path: str) -> None:
        """
        Skriv en rad i Versions för den skapade vattenmärkta filen.
        - documentid: pekar på BASE_PDF:ens Documents-id
        - intended_for: 'RMAP'
        - secret: samma bytes som link (UNHEX)
        - method: t.ex. 'RMAPBest'
        - position: t.ex. 'bottom-right'
        - path: full sökväg på disk under STORAGE_DIR
        """
        document_id = _ensure_document_for_path(str(BASE_PDF), owner_id=1)
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, secret, method, position, path)
                    VALUES (:documentid, :link, :intended_for, :secret_hex, :method, :position, :path)
                """),
                {
                    "documentid": int(document_id),
                    "link": link_hex.lower(),
                    "intended_for": "RMAP",
                    "secret_hex": link_hex.lower(),   # samma 32 byte som link representerar
                    "method": "Our method",
                    "position": "none",
                    "path": str(path),
                },
            )


    # --- /rmap-initiate: pass-through av base64 till RMAP, returnera RMAP:s base64 ---
    @app.route("/rmap-initiate", methods=["POST"])
    def rmap_initiate():
        incoming = request.get_json(force=True, silent=True) or {}
        b64 = (incoming.get("payload") or "").strip()
        if not b64:
            return jsonify({"error": "Missing 'payload'"}), 400

        try:
            # Skicka base64 direkt – RMAP gör base64→PGP→JSON internt
            resp = rmap.handle_message1({"payload": b64})
        except Exception as e:
            return jsonify({"error": f"Invalid Message1: {e}"}), 400

        # RMAP bör ge {"payload":"<base64>"} eller ev. en str med base64
        if isinstance(resp, dict) and isinstance(resp.get("payload"), str):
            return jsonify({"payload": resp["payload"]}), 200
        elif isinstance(resp, (str, bytes)):
            out = resp.decode() if isinstance(resp, bytes) else resp
            return jsonify({"payload": out}), 200

        return jsonify({"error": "RMAP message1 did not return a PGP payload",
                        "debug": str(resp)[:200]}), 400



    # --- /rmap-get-link: pass-through av base64 till RMAP, bygg 32-hex av noncerna ---
    @app.route("/rmap-get-link", methods=["POST"])
    def rmap_get_link():
        incoming = request.get_json(force=True, silent=True) or {}
        b64 = (incoming.get("payload") or "").strip()
        if not b64:
            return jsonify({"error": "Missing 'payload'"}), 400

        try:
            session_info = rmap.handle_message2({"payload": b64})
        except Exception as e:
            return jsonify({"error": f"Invalid Message2: {e}"}), 400

        if isinstance(session_info, (str, bytes)):
            s = session_info.decode() if isinstance(session_info, bytes) else session_info
            s = s.strip()
            try:
                session_info = json.loads(s)
            except Exception:
                if len(s) == 32 and all(c in "0123456789abcdef" for c in s.lower()):
                    try:
                        ns = int(s[16:], 16)
                    except ValueError:
                        return jsonify({"error": "Invalid hex in Message2 string"}), 400
                    identity = _identity_from_ns(ns)
                    pdf_path = _create_rmap_watermarked_pdf(s, identity=identity)
                    _store_rmap_version(s, pdf_path)
                    return jsonify({"result": s}), 200
                return jsonify({"error": "Unexpected Message2 string", "debug": s[:200]}), 400



        if isinstance(session_info, dict):
            # if its already a link /Sandra
            maybe_result = session_info.get("result") or session_info.get("link")
            if isinstance(maybe_result, str):
                s = maybe_result.strip()
                if len(s) == 32 and all(c in "0123456789abcdef" for c in s.lower()):
                    ns = int(s[16:], 16)
                    identity = _identity_from_ns(ns)
                    pdf_path = _create_rmap_watermarked_pdf(s, identity=identity)
                    _store_rmap_version(s, pdf_path)
                    return jsonify({"result": s}), 200


            # 2) annars, bygg 32-hex av noncer (snake/camel + str/int)
            def _get_int(d, *keys):
                v = None
                for k in keys:
                    if k in d:
                        v = d[k]
                        break
                if isinstance(v, int):
                    return v
                if isinstance(v, str):
                    v = v.strip()
                    for base in (10, 16):
                        try:
                            return int(v, base)
                        except ValueError:
                            pass
                return None

            nc = _get_int(session_info, "nonce_client", "nonceClient")
            ns = _get_int(session_info, "nonce_server", "nonceServer")
            if isinstance(nc, int) and isinstance(ns, int):
                link_hex = f"{nc:016x}{ns:016x}"
                identity = _identity_from_ns(ns)
                pdf_path = _create_rmap_watermarked_pdf(link_hex, identity=identity)
                _store_rmap_version(link_hex, pdf_path)
                return jsonify({"result": link_hex}), 200 #returns the link /Sandra


        return jsonify({"error": "Invalid session info (missing nonces)",
                        "debug": session_info}), 400


    def _identity_from_ns(ns: int) -> str | None:
        """
        Försök hitta identity via nonceServer (ns) i RMAP:s in-memory state.
        RMAP håller self.nonces: {identity: (nonceClient, nonceServer)} / Sandra
        """
        try:
            for ident, pair in getattr(rmap, "nonces", {}).items():
                if isinstance(pair, (tuple, list)) and len(pair) == 2 and int(pair[1]) == int(ns):
                    return ident
        except Exception:
            pass
        return None






    #added this for the brute-force thing aka. flask_limiter /Sandra
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify(error="rate_limited", detail=str(e.description)), 429



    return app
    

# WSGI entrypoint
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
