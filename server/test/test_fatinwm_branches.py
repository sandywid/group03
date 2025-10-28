# test/test_fatinwm_branches.py
import io
import importlib
from pathlib import Path
import tempfile
import pytest

# Importera modulen först när testet körs (hjälper mot "module-not-measured")
def _mod():
    return importlib.import_module("src.fatinWM")

MINIMAL_PDF = b"%PDF-1.4\n%...\n%%EOF\n"

def _make_marked(secret: str, key: str) -> bytes:
    FatinWM = _mod().FatinWM
    return FatinWM().add_watermark(MINIMAL_PDF, secret=secret, key=key, position=None)

# --- r.19–21 + r.20: str-vägen i is_watermark_applicable -------------------
def test_is_applicable_str_true_and_false():
    FatinWM = _mod().FatinWM
    w = FatinWM()
    assert w.is_watermark_applicable("foo.PDF") is True   # träffar r.19->20
    assert w.is_watermark_applicable("foo.txt") is False  # motsatt gren

# --- r.28–32: add_watermark filobjekt + filväg -----------------------------
def test_add_watermark_reads_from_fileobj_and_path():
    FatinWM = _mod().FatinWM
    w = FatinWM()

    # fileobj-gren (r.28–29)
    out1 = w.add_watermark(io.BytesIO(MINIMAL_PDF), secret="S", key="K", position=None)
    assert b"%%FATINWM:" in out1

    # path-gren (r.31–32)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.pdf"
        p.write_bytes(MINIMAL_PDF)
        out2 = w.add_watermark(str(p), secret="S2", key="K", position=None)
        assert b"%%FATINWM:" in out2

# --- r.51–55: read_secret filobjekt + filväg -------------------------------
def test_read_secret_fileobj_and_path():
    FatinWM = _mod().FatinWM
    w = FatinWM()
    key, secret = "K1", "FLAG-OK"
    pdf_bytes = _make_marked(secret, key)

    # fileobj (r.51–52)
    assert w.read_secret(io.BytesIO(pdf_bytes), key) == secret

    # path (r.54–55)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "in.pdf"
        p.write_bytes(pdf_bytes)
        assert w.read_secret(str(p), key) == secret

# --- r.61–62: pos == -1 => SecretNotFoundError ------------------------------
def test_read_secret_raises_when_no_marker():
    FatinWM = _mod().FatinWM
    w = FatinWM()
    # Ta EXAKT samma klassobjekt som funktionen använder
    SecretNotFoundError = FatinWM.read_secret.__globals__["SecretNotFoundError"]
    with pytest.raises(SecretNotFoundError):
        w.read_secret(MINIMAL_PDF, key="K")  # ingen marker alls

# --- r.67–68: end == -1 (ingen newline efter payload) -----------------------
def test_read_secret_end_minus_one_branch():
    fwm = _mod()
    FatinWM = fwm.FatinWM
    w = FatinWM()
    # Skapa payload & bygg en marker-rad UTAN avslutande newline
    payload = w._create_payload("S", "K")
    crafted = MINIMAL_PDF + b"%%FATINWM:" + payload.encode("utf-8")  # ingen \n
    # Hämtar payload trots end == -1 -> sätter end=len(pdf_data)
    assert w.read_secret(crafted, "K") == "S"

# --- r.102–103: korrupt payload -> InvalidKeyError --------------------------
def test_verify_payload_corrupted_raises():
    FatinWM = _mod().FatinWM
    w = FatinWM()
    InvalidKeyError = FatinWM.read_secret.__globals__["InvalidKeyError"]

    key = "K"
    good = _make_marked("S", key)

    # Vänd på base64-payloaden så b64/JSON-dekodning spricker -> except-blocket
    marker = b"%%FATINWM:"
    pos = good.rfind(marker)
    start = pos + len(marker)
    end = good.find(b"\n", start)
    if end == -1:
        end = len(good)
    payload = good[start:end].decode("utf-8")
    bad_payload = payload[::-1]  # enkel sabotage

    corrupted = good[:start] + bad_payload.encode("utf-8") + good[end:]
    with pytest.raises(InvalidKeyError):
        w.read_secret(corrupted, key)

# --- r.114–115: MAC-mismatch -> InvalidKeyError -----------------------------
def test_read_secret_wrong_key_raises_invalidkey():
    FatinWM = _mod().FatinWM
    w = FatinWM()
    InvalidKeyError = FatinWM.read_secret.__globals__["InvalidKeyError"]

    bytes_ok = _make_marked("S", "GOOD")
    with pytest.raises(InvalidKeyError):
        w.read_secret(bytes_ok, "BAD")

# --- r.128–136: _remove_marker specialfall (end == -1, samt newline före) ---
def test__remove_marker_end_minus_one_and_newline_branch():
    FatinWM = _mod().FatinWM
    w = FatinWM()

    # 1) end == -1 (ingen newline efter marker) -> r.128–130
    payload = w._create_payload("S", "K")
    pdf1 = MINIMAL_PDF + b"%%FATINWM:" + payload.encode("utf-8")  # ingen \n
    cleaned1 = w._remove_marker(pdf1)
    assert b"%%FATINWM:" not in cleaned1

    # 2) newline före marker -> r.133–134 (pos flyttas tillbaka) och r.136 return
    pdf2 = MINIMAL_PDF + b"\n%%FATINWM:" + payload.encode("utf-8") + b"\n"
    cleaned2 = w._remove_marker(pdf2)
    assert b"%%FATINWM:" not in cleaned2
    # Kontroll att föregående newline också ryker (behöver inte sluta med extra \n)
    assert cleaned2.endswith(b"%%EOF\n") or cleaned2.endswith(b"%%EOF")

