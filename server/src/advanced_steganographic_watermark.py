#  PDFishAndChipsStamp
#
# advanced_steganographic_watermark.py
#"""
#Basic-stream steganographic watermarking for PDFs.

#- Krypterar 'secret' med key (AES-GCM).
#- Bygger bitström: MAGIC (7B) + 32-bit längd + payload (JSON-bytes).
#- Inbäddning: skriver varje bit i LSB-pariteten av sista siffran i varje tal-token.
#- Utläsning: läser tillbaka i samma ordning.

#Den här filen är självständig och försöker återanvända projektets
#watermarking_method (om den finns) för exceptions/basklass.
#"""

from __future__ import annotations
import os
import re
import json
import base64
import hashlib
import struct
from typing import Iterator, Tuple, Optional


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

# AES-GCM
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:
    AESGCM = None  # höjs vid användning

class AdvancedSteganographicWatermark(WatermarkingMethodBase):
    
    name = "advanced-steganographic"

    # --- Klasskonstanter för basic stream ---
    _MAGIC = b"ADVWM1|"   # 7 bytes
    _LEN_BITS = 32        # 32-bit längdfält
    _HEADER_BITS = len(_MAGIC) * 8 + _LEN_BITS

    # Håller kvar CHUNK_SIZE för kompatibilitet, används ej i stream-läget
    _CHUNK_SIZE = 4

    def __init__(self):
        super().__init__() if hasattr(super(), "__init__") else None

    # ====== Basklassens abstrakta metoder (minimala implementationer) ======
    @staticmethod
    def get_usage() -> str:
        return "PDFishAndChipsStamp"
 

    def is_watermark_applicable(self, pdf, **kwargs) -> bool:
        return True


    # ====== Publika API ======
    def add_watermark(self, pdf, secret: str, key: str, position: Optional[str] = None) -> bytes:
        if not secret or not key:
            raise ValueError("Både secret och key måste vara icke-tomma strängar")

        pdf_bytes = self._load_pdf_bytes(pdf)
        payload = self._prepare_payload(secret, key)
        return self._embed_stream(pdf_bytes, payload)

    def read_secret(self, pdf, key: str) -> str:
        if not key:
            raise ValueError("Key måste vara en icke-tom sträng")

        pdf_bytes = self._load_pdf_bytes(pdf)
        extracted = self._extract_stream(pdf_bytes)
        if not extracted:
            raise SecretNotFoundError("Inget vattenmärke hittades")

        try:
            return self._decrypt_payload(extracted, key)
        except InvalidKeyError:
            raise
        except Exception as e:
            raise InvalidKeyError("Felaktig nyckel eller korrupt vattenmärke") from e

    # ====== Kryptering / payload ======
    def _derive_key(self, key_material: str) -> bytes:
        return hashlib.sha256(key_material.encode("utf-8")).digest()

    def _prepare_payload(self, secret: str, key: str) -> bytes:
        if AESGCM is None:
            raise ModuleNotFoundError("cryptography saknas. Installera med `pip install cryptography`.")

        k = self._derive_key(key)
        aes = AESGCM(k)
        iv = os.urandom(12)  # 96-bit nonce
        ct = aes.encrypt(iv, secret.encode("utf-8"), None)  # ciphertext||tag
        obj = {"data": base64.b64encode(ct).decode("ascii"),
               "iv":   base64.b64encode(iv).decode("ascii")}
        # kompakt JSON
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _decrypt_payload(self, payload_bytes: bytes, key: str) -> str:
        if AESGCM is None:
            raise ModuleNotFoundError("cryptography saknas. Installera med `pip install cryptography`.")
        try:
            obj = json.loads(payload_bytes.decode("utf-8"))
            ct = base64.b64decode(obj["data"])
            iv = base64.b64decode(obj["iv"])
        except Exception as e:
            raise InvalidKeyError("Korrupt eller ogiltigt vattenmärke") from e

        try:
            k = self._derive_key(key)
            aes = AESGCM(k)
            pt = aes.decrypt(iv, ct, None)
            return pt.decode("utf-8")
        except Exception as e:
            raise InvalidKeyError("Felaktig nyckel eller korrupt vattenmärke") from e

    # ====== PDF util ======
    def _load_pdf_bytes(self, pdf) -> bytes:
        if isinstance(pdf, (bytes, bytearray)):
            return bytes(pdf)
        if hasattr(pdf, "read"):
            return pdf.read()
        if isinstance(pdf, str):
            with open(pdf, "rb") as f:
                return f.read()
        raise ValueError("pdf måste vara bytes, file-like eller en sökväg (str)")

    # ====== Token-iterator & paritet ======
    def _iter_numbers(self, data: bytes) -> Iterator[Tuple[re.Match, int, int]]:
        num_pat = rb'[-+]?\d+(?:\.\d+)?'
        for m in re.finditer(num_pat, data):
            yield m, m.start(), m.end()

    def _num_get_parity(self, token: bytes) -> Optional[int]:
        try:
            s = token.decode("ascii", errors="strict")
            if "." in s:
                head, tail = s.split(".", 1)
                if tail and tail[-1].isdigit():
                    return int(tail[-1]) & 1
                return int(head[-1]) & 1
            return (int(s) % 10) & 1
        except Exception:
            return None

    def _num_set_parity(self, token: bytes, want_bit: str) -> bytes:
        want = 1 if want_bit == "1" else 0
        try:
            s = token.decode("ascii", errors="ignore")
        except Exception:
            return token

        # decimal
        if "." in s:
            head, tail = s.split(".", 1)
            if tail and tail[-1].isdigit():
                d = int(tail[-1])
                if (d & 1) != want:
                    d = (d + 1) % 10
                tail = tail[:-1] + str(d)
                return (head + "." + tail).encode("ascii")
        # heltal
        sign = ""
        body = s
        if body and body[0] in "+-":
            sign, body = body[0], body[1:]
        if not body or not body[-1].isdigit():
            return token
        d = int(body[-1])
        if (d & 1) != want:
            d = (d + 1) % 10
        body = body[:-1] + str(d)
        return (sign + body).encode("ascii")

    # ====== Stream-embed / extract ======
    def _embed_stream(self, pdf_bytes: bytes, payload: bytes) -> bytes:
        header = self._MAGIC + struct.pack(">I", len(payload))
        bits = "".join(f"{b:08b}" for b in header) + "".join(f"{b:08b}" for b in payload)

        numbers = list(self._iter_numbers(pdf_bytes))
        if len(numbers) < len(bits):
            raise WatermarkingError(
                f"Use a PDF with more content."
            )

        out = bytearray()
        cursor = 0
        for k, (_, start, end) in enumerate(numbers[:len(bits)]):
            out += pdf_bytes[cursor:start]
            tok = pdf_bytes[start:end]
            want = bits[k]
            cur = self._num_get_parity(tok)
            new_tok = tok if (cur is not None and cur == (1 if want == "1" else 0)) else self._num_set_parity(tok, want)
            out += new_tok
            cursor = end
        out += pdf_bytes[cursor:]
        return bytes(out)

    def _extract_stream(self, pdf_bytes: bytes) -> bytes:
        numbers = list(self._iter_numbers(pdf_bytes))
        if not numbers:
            raise SecretNotFoundError("Inget vattenmärke hittades (inga tal att läsa).")

        # Läs header-bitar
        bits = []
        i = 0
        while len(bits) < self._HEADER_BITS and i < len(numbers):
            _, start, end = numbers[i]
            b = self._num_get_parity(pdf_bytes[start:end])
            if b is not None:
                bits.append(str(b))
            i += 1
        if len(bits) < self._HEADER_BITS:
            raise SecretNotFoundError("Ofullständig header/ingen magic header.")

        # Tolka MAGIC + längd
        header_bytes = bytearray()
        for j in range(0, len(bits), 8):
            header_bytes.append(int("".join(bits[j:j+8]), 2))
        magic = bytes(header_bytes[:len(self._MAGIC)])
        if magic != self._MAGIC:
            raise SecretNotFoundError("Fel eller saknad magic header.")
        length = struct.unpack(">I", bytes(header_bytes[len(self._MAGIC):len(self._MAGIC)+4]))[0]

        # Läs payload-bitar
        need = length * 8
        data_bits = []
        while len(data_bits) < need and i < len(numbers):
            _, start, end = numbers[i]
            b = self._num_get_parity(pdf_bytes[start:end])
            if b is not None:
                data_bits.append(str(b))
            i += 1
        if len(data_bits) < need:
            raise SecretNotFoundError("Ofullständig payload.")

        out = bytearray()
        for j in range(0, len(data_bits), 8):
            out.append(int("".join(data_bits[j:j+8]), 2))
        return bytes(out)

if __name__ == "__main__":
    print("advanced_steganographic_watermark.py")
