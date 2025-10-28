import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject, ArrayObject

from AdnasWM import AdnasWM, CommentStamp, InvalidKeyError


def _pdf_with_stream_array() -> bytes:
    """Create a page whose /Contents is an ARRAY of two content streams."""
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=300)

    s1 = StreamObject(); s1._data = b"q\nQ\n"
    s2 = StreamObject(); s2._data = b"q\nQ\n"
    r1 = w._add_object(s1)
    r2 = w._add_object(s2)

    page[NameObject("/Contents")] = ArrayObject([r1, r2])

    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def _pdf_with_single_stream() -> bytes:
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=300)
    s = StreamObject(); s._data = b"q\nQ\n"
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = s_ref
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_adnaswm_handles_contents_array_and_roundtrips():
    pdf_in = _pdf_with_stream_array()
    wm = AdnasWM()
    secret = "hemlis-🧪"
    key = "nyckel-🗝️"

    pdf_out = wm.add_watermark(pdf_in, secret, key)
    got = wm.read_secret(pdf_out, key)
    assert got == secret


def test_adnaswm_invalid_key_aesgcm_branch():
    # AESGCM should be the default branch if cryptography is installed → check wrong key path
    pdf_in = _pdf_with_single_stream()
    wm = AdnasWM()
    out = wm.add_watermark(pdf_in, "topsecret", "ratt")
    with pytest.raises(InvalidKeyError):
        wm.read_secret(out, "fel")
