# fatinWM.py
"""
FatinWM – Simple watermarking method that works with the Tatou API.
Embeds a secret in PDF by appending after EOF marker.
"""

from watermarking_method import WatermarkingMethod, SecretNotFoundError, InvalidKeyError
import hashlib
import hmac
import json
import base64


class FatinWM(WatermarkingMethod):
    name = "FatinWM"

    def is_watermark_applicable(self, pdf, position: str = None) -> bool:
        """Check if file can be watermarked (must be PDF)."""
        if isinstance(pdf, str):
            return pdf.lower().endswith(".pdf")
        return True  # Assume bytes/file objects are PDFs

    def add_watermark(self, pdf, secret: str, key: str, position: str | None = None) -> bytes:
        """Add watermark to PDF by appending after EOF."""
        # Load PDF bytes
        if isinstance(pdf, (bytes, bytearray)):
            pdf_data = bytes(pdf)
        elif hasattr(pdf, 'read'):
            pdf_data = pdf.read()
        else:
            with open(pdf, "rb") as f:
                pdf_data = f.read()

        # Create secure payload
        payload = self._create_payload(secret, key)
        
        # Create marker to append
        marker = b"\n%%FATINWM:" + payload.encode('utf-8') + b"\n"
        
        # Remove any existing marker
        cleaned = self._remove_marker(pdf_data)
        
        # Append new marker
        return cleaned + marker

    def read_secret(self, pdf, key: str) -> str:
        """Read watermark from PDF."""
        # Load PDF bytes
        if isinstance(pdf, (bytes, bytearray)):
            pdf_data = bytes(pdf)
        elif hasattr(pdf, 'read'):
            pdf_data = pdf.read()
        else:
            with open(pdf, "rb") as f:
                pdf_data = f.read()

        # Find marker
        marker = b"%%FATINWM:"
        pos = pdf_data.rfind(marker)
        
        if pos == -1:
            raise SecretNotFoundError("No watermark found")
        
        # Extract payload
        start = pos + len(marker)
        end = pdf_data.find(b"\n", start)
        if end == -1:
            end = len(pdf_data)
            
        payload = pdf_data[start:end].decode('utf-8')
        
        # Verify and extract secret
        return self._verify_payload(payload, key)

    @staticmethod
    def get_usage() -> str:
        """Return usage description."""
        return "Simple watermarking by appending data after PDF EOF. Requires key and secret."

    def _create_payload(self, secret: str, key: str) -> str:
        """Create authenticated payload with HMAC."""
        # Derive key
        derived_key = hashlib.sha256(key.encode('utf-8')).digest()
        
        # Create HMAC
        mac = hmac.new(derived_key, secret.encode('utf-8'), hashlib.sha256)
        
        # Create payload
        data = {
            "secret": secret,
            "mac": base64.b64encode(mac.digest()).decode('ascii')
        }
        
        # Encode as base64
        return base64.b64encode(json.dumps(data).encode('utf-8')).decode('ascii')

    def _verify_payload(self, payload: str, key: str) -> str:
        """Verify payload and extract secret."""
        try:
            # Decode payload
            data = json.loads(base64.b64decode(payload))
        except Exception:
            raise InvalidKeyError("Corrupted watermark")
        
        # Get secret and MAC
        secret = data.get("secret", "")
        mac_str = data.get("mac", "")
        
        # Verify MAC
        derived_key = hashlib.sha256(key.encode('utf-8')).digest()
        expected_mac = hmac.new(derived_key, secret.encode('utf-8'), hashlib.sha256)
        expected_mac_str = base64.b64encode(expected_mac.digest()).decode('ascii')
        
        if not hmac.compare_digest(mac_str, expected_mac_str):
            raise InvalidKeyError("Invalid key")
        
        return secret

    def _remove_marker(self, pdf_data: bytes) -> bytes:
        """Remove existing watermark marker if present."""
        marker = b"%%FATINWM:"
        pos = pdf_data.rfind(marker)
        
        if pos == -1:
            return pdf_data
            
        # Remove from marker position to end of line
        end = pdf_data.find(b"\n", pos)
        if end == -1:
            return pdf_data[:pos]
        
        # Also remove the newline before marker if present
        if pos > 0 and pdf_data[pos-1:pos] == b"\n":
            pos -= 1
            
        return pdf_data[:pos]