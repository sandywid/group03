import io
import os
import pytest

pytest.importorskip("pypdf")
from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject

# Import the watermark implementation under test
from AdnasWM import AdnasWM, CommentStamp, SecretNotFoundError, InvalidKeyError


def _pdf_with_empty_content_stream() -> bytes:
    """Create a tiny, valid one-page PDF that has a /Contents stream."""
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=300)
    # Add an explicit (empty) content stream so CommentStamp has somewhere to write
    s = StreamObject()
    s._data = b"q\nQ\n"  # minimal no-op graphics ops
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = s_ref

    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_roundtrip_ok_recovers_secret(tmp_path):
    pdf_in = _pdf_with_empty_content_stream()
    wm = AdnasWM()
    secret = "s3cr3t"
    key = "correct-horse-battery-staple"

    pdf_out = wm.add_watermark(pdf_in, secret, key)
    assert isinstance(pdf_out, (bytes, bytearray)) and len(pdf_out) > len(pdf_in)

    recovered = wm.read_secret(pdf_out, key)
    assert recovered == secret


def test_invalid_key_raises():
    pdf_in = _pdf_with_empty_content_stream()
    wm = CommentStamp()
    pdf_out = wm.add_watermark(pdf_in, "topsecret", "right-key")

    with pytest.raises(InvalidKeyError):
        wm.read_secret(pdf_out, "wrong-key")


def test_missing_secret_or_key_raises_valueerror():
    wm = CommentStamp()
    pdf_in = _pdf_with_empty_content_stream()

    with pytest.raises(ValueError):
        wm.add_watermark(pdf_in, secret="", key="k")
    with pytest.raises(ValueError):
        wm.add_watermark(pdf_in, secret="x", key="")


def test_no_watermark_raises_secret_not_found():
    # Build a PDF that we didn't watermark
    pdf_in = _pdf_with_empty_content_stream()
    wm = CommentStamp()

    with pytest.raises(SecretNotFoundError):
        wm.read_secret(pdf_in, key="any")
