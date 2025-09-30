# AdnasWM.py — CommentStamp (invisible, stream-aware)
"""
Invisible WM via PDF comment in a content stream.

We add one line into (the first) page’s content stream:
    % LCPWM1|<base64(payload-bytes)>

PDF renderers ignore comments → no visual change.
"""
from __future__ import annotations
import os
import io
import json
import base64
import hashlib
import hmac
import struct
from typing import Optional, List

try:
    import watermarking_method
    WatermarkingMethodBase = getattr(watermarking_method, "WatermarkingMethod", object)
    WatermarkingError = getattr(watermarking_method, "WatermarkingError", Exception)
    SecretNotFoundError = getattr(watermarking_method, "SecretNotFoundError", Exception)
    InvalidKeyError = getattr(watermarking_method, "InvalidKeyError", Exception)
except Exception:
    WatermarkingMethodBase = object
    class WatermarkingError(Exception): pass
    class SecretNotFoundError(Exception): pass
    class InvalidKeyError(Exception): pass

# ---- encryption ----
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:
    AESGCM = None

# ---- pypdf ----
from pypdf import PdfReader, PdfWriter
from pypdf.generic import IndirectObject, ArrayObject, StreamObject, NameObject

def hmac_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    res = 0
    for x, y in zip(a.encode("utf-8", errors="ignore"), b.encode("utf-8", errors="ignore")):
        res |= x ^ y
    return res == 0


class CommentStamp(WatermarkingMethodBase):

    name = "LiteralCharParityStamp"  

    _MAGIC = b"LCPWM1|"  
    _TAG_PREFIX = b"% " + _MAGIC   
    # ---- Crypto/payload ----
    def _derive_key(self, key_material: str) -> bytes:
        return hashlib.sha256(key_material.encode("utf-8")).digest()

    def _prepare_payload(self, secret: str, key: str) -> bytes:
        k = self._derive_key(key)
        if AESGCM is not None:
            aes = AESGCM(k)
            iv = os.urandom(12)
            ct = aes.encrypt(iv, secret.encode("utf-8"), None)  
            obj = {"enc": True,
                   "iv": base64.b64encode(iv).decode("ascii"),
                   "data": base64.b64encode(ct).decode("ascii")}
        else:
            mac = base64.b64encode(hmac.new(k, secret.encode("utf-8"), hashlib.sha256).digest()).decode("ascii")
            obj = {"enc": False, "secret": secret, "mac": mac}
        # header (MAGIC + len) + JSON-bytes
        payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        header = self._MAGIC + struct.pack(">I", len(payload))
        return header + payload

    def _decrypt_payload(self, blob: bytes, key: str) -> str:
        # blob = MAGIC(7) + len(4) + JSON
        if not blob.startswith(self._MAGIC) or len(blob) < len(self._MAGIC) + 4:
            raise SecretNotFoundError("Magic header mismatch")
        ln = struct.unpack(">I", blob[len(self._MAGIC):len(self._MAGIC)+4])[0]
        json_bytes = blob[len(self._MAGIC)+4:]
        if len(json_bytes) != ln:
            raise SecretNotFoundError("Length mismatch")
        try:
            obj = json.loads(json_bytes.decode("utf-8"))
        except Exception as e:
            raise InvalidKeyError("Malformed payload JSON") from e

        k = self._derive_key(key)
        if obj.get("enc"):
            if AESGCM is None:
                raise InvalidKeyError("Encrypted payload but 'cryptography' not installed")
            try:
                iv = base64.b64decode(obj["iv"]); ct = base64.b64decode(obj["data"])
                return AESGCM(k).decrypt(iv, ct, None).decode("utf-8")
            except Exception as e:
                raise InvalidKeyError("Decryption failed") from e
        else:
            secret = obj.get("secret"); mac = obj.get("mac")
            if secret is None or mac is None:
                raise InvalidKeyError("Missing fields in payload")
            expect = base64.b64encode(hmac.new(k, secret.encode("utf-8"), hashlib.sha256).digest()).decode("ascii")
            if not hmac_compare(mac, expect):
                raise InvalidKeyError("HMAC mismatch")
            return secret

    # ---- pypdf stream access ----
    def _get_content_stream_objects(self, page) -> List[StreamObject]:
        streams: List[StreamObject] = []
        contents = page.get("/Contents")
        if contents is None:
            return streams

        def _resolve(obj):
            return obj.get_object() if isinstance(obj, IndirectObject) else obj

        if isinstance(contents, ArrayObject):
            for obj in contents:
                s = _resolve(obj)
                if isinstance(s, StreamObject):
                    streams.append(s)
        else:
            s = _resolve(contents)
            if isinstance(s, StreamObject):
                streams.append(s)
        return streams

    def _replace_stream_data(self, writer: PdfWriter, page, old_stream_obj: StreamObject, new_data: bytes):
        new_stream = StreamObject()
        new_stream.set_data(new_data)  
        new_ref = writer._add_object(new_stream)

        contents = page.get("/Contents")

        def _resolve(obj):
            return obj.get_object() if isinstance(obj, IndirectObject) else obj

        if isinstance(contents, ArrayObject):
            for i, obj in enumerate(contents):
                if _resolve(obj) is old_stream_obj:
                    contents[i] = new_ref
            page[NameObject("/Contents")] = contents
        else:
            page[NameObject("/Contents")] = new_ref

    # ---- Public API ----
    @staticmethod
    def get_usage() -> str:
        return "Enter key & secret; position ignored."

    def is_watermark_applicable(self, pdf, **kwargs) -> bool:
        return True

    def add_watermark(self, pdf, secret: str, key: str, position: Optional[str] = None) -> bytes:
        """
        Bäddar in ett osynligt WM som en PDF-kommentar i första tillgängliga content stream.
        """
        if not secret or not key:
            raise ValueError("Both secret and key are required")

        if isinstance(pdf, (bytes, bytearray)):
            reader = PdfReader(io.BytesIO(pdf))
        elif hasattr(pdf, "read"):
            reader = PdfReader(pdf)
        else:
            reader = PdfReader(pdf)

        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)

        target_page = None
        target_stream = None
        for page in writer.pages:
            streams = self._get_content_stream_objects(page)
            if streams:
                target_page = page
                target_stream = streams[0]
                break
        if target_page is None:
            raise WatermarkingError("No content streams found")

        payload = self._prepare_payload(secret, key)
        tag = self._TAG_PREFIX + base64.b64encode(payload) + b"\n"

        try:
            data = target_stream.get_data()  
        except Exception as e:
            raise WatermarkingError(f"Could not access content stream: {e}")

        if not (len(data) and data.endswith((b"\n", b"\r"))):
            data = data + b"\n"
        new_data = data + tag

        self._replace_stream_data(writer, target_page, target_stream, new_data)

        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def read_secret(self, pdf, key: str) -> str:
        """
        Söker vår kommentar i alla content streams i dokumentordning.
        """
        if not key:
            raise ValueError("Key required")

        if isinstance(pdf, (bytes, bytearray)):
            reader = PdfReader(io.BytesIO(pdf))
        elif hasattr(pdf, "read"):
            reader = PdfReader(pdf)
        else:
            reader = PdfReader(pdf)

        for p in reader.pages:
            streams = self._get_content_stream_objects(p)
            for s in streams:
                try:
                    data = s.get_data()
                except Exception:
                    continue
                idx = data.find(self._TAG_PREFIX)
                if idx != -1:
                    line = data[idx + len(self._TAG_PREFIX):].splitlines()[0]
                    try:
                        blob = base64.b64decode(line, validate=True)
                    except Exception:
                        continue
                    return self._decrypt_payload(blob, key)

        raise SecretNotFoundError("Watermark not found")


# --- Alias for watermarking_utils.py ---
class AdnasWM(CommentStamp):
    pass

__all__ = ["CommentStamp", "AdnasWM", "LiteralCharParityStamp"]