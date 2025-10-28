import io
import base64
import struct
import pytest

from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject

from AdnasWM import CommentStamp, AdnasWM, SecretNotFoundError, InvalidKeyError
import AdnasWM as adnas_mod


def _pdf_no_contents() -> bytes:
    """En sida utan /Contents-key (pypdf gör detta som standard)."""
    w = PdfWriter()
    w.add_blank_page(width=300, height=300)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def _pdf_with_stream(data: bytes) -> bytes:
    """En sida med explicit content stream (kan styra newline etc)."""
    w = PdfWriter()
    page = w.add_blank_page(width=300, height=300)
    s = StreamObject()
    s._data = data  # exakt det vi sätter in
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = s_ref
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def test_read_secret_requires_key():
    wm = CommentStamp()
    with pytest.raises(ValueError):
        wm.read_secret(_pdf_no_contents(), key="")


def test_add_watermark_requires_stream_and_appends_newline_if_missing():
    # Ström utan avslutande newline => koden ska lägga till newline innan taggen
    initial = b"q\nQ"  # notera: ingen newline på slutet
    pdf_in = _pdf_with_stream(initial)

    wm = CommentStamp()
    out = wm.add_watermark(pdf_in, secret="s", key="k")  # ska ej krascha

    # Verifiera att strömmen faktiskt slutade med vår tagg på ny rad
    # (Minimal kontroll: PDF-bytesen innehåller vår tagg-prefix)
    assert b"% LCPWM1|" in out


def test_add_watermark_raises_when_no_content_streams():
    pdf_in = _pdf_no_contents()
    wm = CommentStamp()
    with pytest.raises(Exception):  # WatermarkingError
        wm.add_watermark(pdf_in, "s", "k")


def test_roundtrip_hmac_fallback_when_AESGCM_absent(monkeypatch):
    # Simulera att 'cryptography' saknas => HMAC-fallback ska användas
    monkeypatch.setattr(adnas_mod, "AESGCM", None, raising=False)

    wm = CommentStamp()
    pdf_in = _pdf_with_stream(b"q\nQ\n")
    out = wm.add_watermark(pdf_in, "hemlis", "nyckel")
    # roundtrip ska fungera
    assert wm.read_secret(out, "nyckel") == "hemlis"


def test_invalid_key_for_hmac_payload(monkeypatch):
    monkeypatch.setattr(adnas_mod, "AESGCM", None, raising=False)
    wm = CommentStamp()
    pdf_in = _pdf_with_stream(b"q\nQ\n")
    out = wm.add_watermark(pdf_in, "hemlis", "ratt")
    with pytest.raises(InvalidKeyError):
        wm.read_secret(out, "fel")


def test_malformed_payload_json_raises_invalidkey():
    # Bygg en tagg där base64(blob) dekodar till MAGIC + len + *trasig JSON*
    magic = b"LCPWM1|"
    bad_json = b"not-json"
    blob = magic + struct.pack(">I", len(bad_json)) + bad_json
    tag_line = b"% " + magic + base64.b64encode(blob) + b"\n"

    pdf_in = _pdf_with_stream(b"q\nQ\n" + tag_line)
    wm = CommentStamp()
    with pytest.raises(InvalidKeyError):
        wm.read_secret(pdf_in, "k")


def test_length_mismatch_raises_secret_not_found():
    # MAGIC + fel längd => ska ge SecretNotFoundError
    magic = b"LCPWM1|"
    payload = b"{}"
    wrong_len = struct.pack(">I", len(payload) + 5)  # medvetet fel
    blob = magic + wrong_len + payload
    tag_line = b"% " + magic + base64.b64encode(blob) + b"\n"

    pdf_in = _pdf_with_stream(b"q\nQ\n" + tag_line)
    wm = AdnasWM()
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(pdf_in, "k")


def test_magic_mismatch_raises_secret_not_found():
    # Fel "magic" i blobben — fortfarande korrekt base64, men fel header
    bad_magic = b"NOTMAG|"
    payload = b"{}"
    blob = bad_magic + struct.pack(">I", len(payload)) + payload
    tag_line = b"% LCPWM1|" + base64.b64encode(blob) + b"\n"  # Prefixen matchar → blob läses

    pdf_in = _pdf_with_stream(b"q\nQ\n" + tag_line)
    wm = CommentStamp()
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(pdf_in, "k")
