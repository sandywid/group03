# invisible_text.py
from __future__ import annotations
import base64, hashlib, hmac, io
from typing import Optional
import fitz  # PyMuPDF

from watermarking_method import (
    WatermarkingMethod, WatermarkingError,
    SecretNotFoundError, InvalidKeyError, load_pdf_bytes
)


class InvisibleTextWatermark(WatermarkingMethod):
    """
    Embed an authenticated payload as invisible text in each page's content stream.

    - Uses near-zero opacity (still present in text layer).
    - Authenticates (HMAC-SHA256) the secret with key to prevent spoofing.
    - No file I/O; operates on bytes only.

    name: "invisible-text"
    """

    name = "invisible-text"
    description = "Hides an HMAC-authenticated payload as near-invisible text on each page."

    _MARKER_START = "⟦WMIT1⟧"
    _MARKER_END = "⟦/WMIT1⟧"

    def get_usage(self) -> str:
        return (
            "Embed/read secret via invisible text. Parameters:\n"
            '- "position": "top-left" | "bottom-right" | "center" (optional)\n'
            '- "key": HMAC key (required)\n'
            '- "secret": string to embed (required when embedding)\n'
            "Example create: {\"method\":\"invisible-text\",\"position\":\"center\",\"key\":\"K\",\"secret\":\"S\"}\n"
            "Example read: {\"method\":\"invisible-text\",\"position\":\"center\",\"key\":\"K\"}"
        )

    # ---------- helpers ----------

    def _mac_hex(self, secret_bytes: bytes, key: str) -> str:
        return hmac.new(key.encode("utf-8"), secret_bytes, hashlib.sha256).hexdigest()

    def _pack_payload(self, secret: str, key: str) -> str:
        secret_b = secret.encode("utf-8")
        mac = self._mac_hex(secret_b, key)
        blob = base64.urlsafe_b64encode(secret_b).decode("ascii")
        return f"{self._MARKER_START}{mac}:{blob}{self._MARKER_END}"

    def _unpack_payload(self, text: str, key: str) -> str:
        start = text.find(self._MARKER_START)
        end = text.find(self._MARKER_END, start + 1)
        if start < 0 or end < 0:
            raise SecretNotFoundError("InvisibleText: markers not found")
        payload = text[start + len(self._MARKER_START):end]
        try:
            mac_hex, b64 = payload.split(":", 1)
        except ValueError:
            raise WatermarkingError("InvisibleText: malformed payload")
        secret_b = base64.urlsafe_b64decode(b64.encode("ascii"))
        expect = self._mac_hex(secret_b, key)
        if not hmac.compare_digest(mac_hex, expect):
            raise InvalidKeyError("InvisibleText: HMAC mismatch (bad key?)")
        return secret_b.decode("utf-8")

    def _anchor_point(self, rect: fitz.Rect, position: Optional[str]) -> tuple[float, float]:
        pos = (position or "center").lower()
        if pos == "top-left":
            return rect.x0 + 10, rect.y0 + 10
        if pos == "bottom-right":
            return rect.x1 - 10, rect.y1 - 10
        # default center
        return rect.x0 + rect.width / 2, rect.y0 + rect.height / 2

    # ---------- interface required by Tatou ----------

    def add_watermark(
        self,
        pdf: bytes | io.BufferedIOBase | str,
        *,
        secret: str,
        key: str,
        position: Optional[str] = None,
        **_: object,
    ) -> bytes:
        """Embed secret text in the PDF."""
        if not key:
            raise InvalidKeyError("Missing key")
        if not secret:
            raise WatermarkingError("Missing secret")

        data = load_pdf_bytes(pdf)
        doc = fitz.open(stream=data, filetype="pdf")
        payload = self._pack_payload(secret, key)

        for page in doc:
            x, y = self._anchor_point(page.rect, position)
            page.insert_text(
                (x, y),
                payload,
                fontsize=0.1,
                render_mode=0,      # fill
                fill_opacity=0.02,  # nearly invisible
                rotate=0,
                overlay=True,
            )

        out = io.BytesIO()
        doc.save(out, deflate=True, clean=True)
        doc.close()
        return out.getvalue()

    def read_secret(
        self,
        pdf: bytes | io.BufferedIOBase | str,
        *,
        key: str,
        position: Optional[str] = None,
        **_: object,
    ) -> str:
        """Recover secret text from the PDF."""
        if not key:
            raise InvalidKeyError("Missing key")

        data = load_pdf_bytes(pdf)
        doc = fitz.open(stream=data, filetype="pdf")

        try:
            for page in doc:
                txt = page.get_text("text")
                if self._MARKER_START in txt:
                    result = self._unpack_payload(txt, key)
                    return result
        finally:
            doc.close()

        raise SecretNotFoundError("InvisibleText: no payload found")

    def is_watermark_applicable(
        self,
        pdf: bytes | io.BufferedIOBase | str,
        position: Optional[str] = None,
        **_: object,
    ) -> bool:
        """For now, always return True."""
        return True
