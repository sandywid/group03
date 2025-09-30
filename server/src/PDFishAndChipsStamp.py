# PDFishAndChipsStamp.py


from __future__ import annotations

import os
import io
import re
import uuid
import json
import base64
import hashlib
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---- Exceptions (matchar projektets förväntningar) ----
class WatermarkingError(Exception): ...
class SecretNotFoundError(Exception): ...
class InvalidKeyError(Exception): ...

# ---- Backends ----
try:
    import pikepdf  # type: ignore
    from pikepdf import Name, Dictionary
    HAVE_PIKEPDF = True
except Exception:
    HAVE_PIKEPDF = False


@dataclass
class Result:
    pages_streamed: int
    xmp_ok: bool
    attachment_ok: bool


class PDFishAndChipsStamp:
    name = "PDFishAndChipsStamp"

    @staticmethod
    def get_usage() -> str:
        return "Please enter your secret and key"
    
    def is_watermark_applicable(self, pdf, **kwargs) -> bool:
        return True

    def __init__(self, tag: bytes = b"FISHANDCHIPS"):
        if not HAVE_PIKEPDF:
            raise ModuleNotFoundError("pikepdf is required. Install with: pip install pikepdf")
        self.tag = tag
        uid = uuid.uuid4().hex[:8]
        self.xmp_namespace_uri = f"urn:uuid:{uuid.uuid4()}"
        self.xmp_prefix = f"ns{uid}"
        self.xmp_key = f"{self.xmp_prefix}:d"
        self.embedded_filename = f"._meta{uid}.bin"

    # === Kompatibilitets-anrop ===
    def add_watermark(self, *args, **kwargs):
        """
        Compat:
        - Old style: add_watermark(pdf, secret: str, key: str, position: Optional[str]=None) -> bytes
        - Old style via kwargs: add_watermark(pdf=..., secret=..., key=..., position=None) -> bytes
        - New style: add_watermark(in_pdf=..., out_pdf=..., payload=..., all_pages=True, ...) -> Result
        """
        # 1) gammal stil – positionella argument
        if len(args) >= 3 and isinstance(args[1], str) and isinstance(args[2], str):
            pdf = args[0]
            secret = args[1]
            key = args[2]
            # position ignoreras i nya metoden
            return self._add_legacy_wrapper(pdf, secret, key)

        # 2) gammal stil – kwargs
        if all(k in kwargs for k in ("pdf", "secret", "key")):
            pdf = kwargs.get("pdf")
            secret = kwargs.get("secret")
            key = kwargs.get("key")
            return self._add_legacy_wrapper(pdf, secret, key)

        # 3) ny stil
        return self._add_watermark_newstyle(*args, **kwargs)

    def _add_legacy_wrapper(self, pdf, secret: str, key: str) -> bytes:
        if not secret or not key:
            raise ValueError("Both secret and key are required fields")
        payload = self._prepare_payload(str(secret), str(key))
        # bädda in med nya backenden och returnera bytes
        if isinstance(pdf, (bytes, bytearray)):
            doc = pikepdf.Pdf.open(io.BytesIO(pdf))
        else:
            doc = pikepdf.Pdf.open(pdf)
        try:
            payload_b64 = base64.b64encode(payload)
            # 1) kommentars-stream på första sidan
            _ = self._embed_stream_comments(doc, payload_b64, all_pages=False)
            # 2) XMP
            _ = self._embed_xmp(doc, payload_b64)
            # 3) Embedded file
            _ = self._embed_attachment(doc, payload)
            out = io.BytesIO()
            doc.save(out)
            return out.getvalue()
        finally:
            doc.close()

    # === Ny-stil API ===
    def _add_watermark_newstyle(self, in_pdf=None, out_pdf=None, payload=None, *, all_pages=True, **kwargs) -> Result:
        # --- kompatibilitet med gamla nyckelord ---
        if in_pdf is None:
            in_pdf = (kwargs.get("pdf") or kwargs.get("input_pdf") or
                    kwargs.get("src") or kwargs.get("source"))
        if out_pdf is None:
            out_pdf = (kwargs.get("out_pdf") or kwargs.get("output_pdf") or
                        kwargs.get("dst") or kwargs.get("dest") or kwargs.get("destination"))
        if payload is None:
            payload = (kwargs.get("payload") or kwargs.get("payload_bytes") or
                        kwargs.get("data") or kwargs.get("content") or kwargs.get("watermark"))

        if in_pdf is None:
            raise WatermarkingError("Missing input PDF (use in_pdf=/pdf=/input_pdf=/src=/source=).")
        if payload is None:
            raise WatermarkingError("Missing payload (use payload=/payload_bytes=/data=).")
        if out_pdf is None:
            root, ext = os.path.splitext(str(in_pdf))
            out_pdf = f"{root}.wm{ext or '.pdf'}"

        payload_b64 = base64.b64encode(payload)
        with pikepdf.Pdf.open(in_pdf) as pdf:
            # 1) comment-only stream
            pages_streamed = self._embed_stream_comments(pdf, payload_b64, all_pages)
            # 2) XMP
            x_ok = self._embed_xmp(pdf, payload_b64)
            # 3) embedded file
            a_ok = self._embed_attachment(pdf, payload)
            pdf.save(out_pdf)
            return Result(pages_streamed, x_ok, a_ok)

    # ====== Backward-compat helpers (encryption+payload) ======
    def _derive_key(self, key: str) -> bytes:
        # Enkel, deterministisk 256-bit nyckel av användarnyckeln
        return hashlib.sha256(key.encode("utf-8")).digest()

    def _prepare_payload(self, secret: str, key: str) -> bytes:
        k = self._derive_key(key)
        aes = AESGCM(k)
        iv = os.urandom(12)  # 96-bit nonce
        ct = aes.encrypt(iv, secret.encode("utf-8"), None)
        obj = {"data": base64.b64encode(ct).decode("ascii"),
               "iv":   base64.b64encode(iv).decode("ascii")}
        # kompakt JSON
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _decrypt_payload(self, payload_bytes: bytes, key: str) -> str:
        try:
            obj = json.loads(payload_bytes.decode("utf-8"))
            ct = base64.b64decode(obj["data"])
            iv = base64.b64decode(obj["iv"])
        except Exception as e:
            raise InvalidKeyError("Corrupted or invalid watermark") from e

        try:
            k = self._derive_key(key)
            aes = AESGCM(k)
            pt = aes.decrypt(iv, ct, None)
            return pt.decode("utf-8")
        except Exception as e:
            raise InvalidKeyError("Invalid key or corrupted watermark") from e

    # ====== Public API ======
    def read_secret(self, pdf, key: str) -> str:
        if not key:
            raise ValueError("Key is required")

        # 1) försök via embedded file
        data = None
        doc = None
        if isinstance(pdf, (bytes, bytearray)):
            doc = pikepdf.Pdf.open(io.BytesIO(pdf))
        else:
            doc = pikepdf.Pdf.open(pdf)
        try:
            names = doc.Root.get("/Names")
            if names:
                ef = names.get("/EmbeddedFiles")
                if ef:
                    arr = list(ef.get("/Names", []))
                    for i in range(0, len(arr), 2):
                        if arr[i] == self.embedded_filename:
                            filespec = arr[i+1]
                            stream = filespec.get("/EF").get("/F")
                            data = bytes(stream.read_bytes())
                            break
            # 2) XMP
            if data is None:
                try:
                    md = doc.open_metadata()
                    b64 = md.get(self.xmp_key)
                    if isinstance(b64, str):
                        data = base64.b64decode(b64.encode("ascii"))
                except Exception:
                    pass
            # 3) kommentars-stream (första sidan)
            if data is None:
                try:
                    page = doc.pages[0]
                    contents = page.get("/Contents")
                    streams = []
                    if contents is None:
                        streams = []
                    else:
                        if isinstance(contents, pikepdf.Array):
                            streams = [s for s in contents]
                        else:
                            streams = [contents]
                    tag = b"%% " + self.tag + b"|"
                    for s in streams:
                        bts = bytes(s.read_bytes())
                        pos = bts.find(tag)
                        if pos != -1:
                            part = bts[pos+len(tag):]
                            nl = part.find(b"\\n")
                            b64 = part[:nl] if nl != -1 else part
                            data = base64.b64decode(b64.strip())
                            break
                except Exception:
                    pass
        finally:
            if doc is not None:
                doc.close()

        if data is None:
            raise SecretNotFoundError("No watermark found.")
        return self._decrypt_payload(data, key)

    # ---------------- intern ----------------
    def _embed_stream_comments(self, pdf: 'pikepdf.Pdf', payload_b64: bytes, all_pages: bool) -> int:
        comment = b"\\n%% " + self.tag + b"|" + payload_b64 + b"\\n"
        touched = 0
        targets = range(len(pdf.pages)) if all_pages else [0]
        for i in targets:
            page = pdf.pages[i]
            new_stream = pdf.make_stream(comment)
            contents = page.get("/Contents")
            if contents is None:
                page[Name("/Contents")] = new_stream
            else:
                try:
                    arr = contents
                    if not isinstance(arr, pikepdf.Array):
                        arr_new = pikepdf.Array([contents, new_stream])
                        page[Name("/Contents")] = arr_new
                    else:
                        arr.append(new_stream)
                except Exception:
                    page[Name("/Contents")] = pikepdf.Array([contents, new_stream])
            touched += 1
        return touched

    def _embed_xmp(self, pdf: 'pikepdf.Pdf', payload_b64: bytes) -> bool:
        try:
            md = pdf.open_metadata()
            md.register_namespace(self.xmp_namespace_uri, self.xmp_prefix)
            md[self.xmp_key] = payload_b64.decode("ascii")
            md.save()
            return True
        except Exception:
            return False

    def _embed_attachment(self, pdf: 'pikepdf.Pdf', payload: bytes) -> bool:
        try:
            stream = pdf.make_stream(payload)
            stream["/Type"] = Name("/EmbeddedFile")
            filespec = Dictionary({
                Name("/Type"): Name("/Filespec"),
                Name("/F"): self.embedded_filename,
                Name("/EF"): Dictionary({Name("/F"): stream}),
            })
            names = pdf.Root.get("/Names", Dictionary())
            ef = names.get("/EmbeddedFiles")
            if not ef:
                ef = Dictionary({Name("/Names"): pikepdf.Array([])})
            arr = ef.get("/Names")
            if not isinstance(arr, pikepdf.Array):
                arr = pikepdf.Array([])
            arr.append(self.embedded_filename)
            arr.append(pdf.add_object(filespec))
            ef[Name("/Names")] = arr
            names[Name("/EmbeddedFiles")] = pdf.add_object(ef)
            pdf.Root[Name("/Names")] = pdf.add_object(names)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    print("PDFishAndChipsStamp.py")
