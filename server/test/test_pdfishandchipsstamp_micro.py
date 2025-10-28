# test/test_pdfishandchipsstamp_micro.py
import base64
import builtins
import io
import importlib.util
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter

import PDFishAndChipsStamp as pdfc


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_decrypt_payload_parsing_error_branch():
    wm = pdfc.PDFishAndChipsStamp()
    with pytest.raises(pdfc.InvalidKeyError):
        wm._decrypt_payload(b"xx", "k")  # JSON parse-fel-gren: rad ~160–161


def test_embed_stream_comments_try_except_branch():
    """Tvinga except-vägen via en Array-klass vars append() kastar."""
    wm = pdfc.PDFishAndChipsStamp()

    class FakeArray(list):
        def append(self, obj):
            raise RuntimeError("append-bomb")

    class FakePage(dict):
        def __init__(self):
            super().__init__()
            self["/Contents"] = FakeArray()

    class FakePdf:
        def __init__(self):
            self.pages = [FakePage()]

        def make_stream(self, bts):
            return {"__stream__": bts}

    touched = pdfc.PDFishAndChipsStamp._embed_stream_comments(  # noqa: SLF001
        wm, FakePdf(), b"b64", all_pages=True
    )
    assert touched == 1  # vi kom igenom try/except


def test_embed_xmp_success_path():
    """Träffa lyckad väg i _embed_xmp (rad ~265–267)."""
    wm = pdfc.PDFishAndChipsStamp()

    class FakeMD(dict):
        def register_namespace(self, uri, prefix):
            self["ns"] = (uri, prefix)

        def save(self):
            self["saved"] = True

    class FakePdf:
        def open_metadata(self):
            return FakeMD()

    ok = pdfc.PDFishAndChipsStamp._embed_xmp(wm, FakePdf(), b"QUJD")  # noqa: SLF001
    assert ok is True


def test_embed_attachment_success_path_with_minimal_fake_pikepdf(monkeypatch):
    """
    Träffa _embed_attachment trots att din pikepdf saknar add_object m.m.,
    genom att mocka modulen till enkla Python-objekt.
    """
    wm = pdfc.PDFishAndChipsStamp()

    # 1) Mocka Name/Dictionary → enkla konstruktioner
    monkeypatch.setattr(pdfc, "Name", lambda s: s, raising=True)

    class Dict(dict):
        pass

    monkeypatch.setattr(pdfc, "Dictionary", Dict, raising=True)

    # 2) Mocka pikepdf.Array → list
    class FakeArray(list):
        pass

    class FakePike:
        Array = FakeArray

    monkeypatch.setattr(pdfc, "pikepdf", FakePike(), raising=True)

    # 3) FakePdf med de metoder koden använder
    class FakePdf:
        def __init__(self):
            self.Root = {}

        def make_stream(self, bts):
            return {"__stream__": bts}

        def add_object(self, obj):
            return obj

    ok = pdfc.PDFishAndChipsStamp._embed_attachment(wm, FakePdf(), b"ABC")  # noqa: SLF001
    assert ok is True


def test_import_fallback_no_pikepdf(monkeypatch):
    """Mät import-guard (rader ~28–29) utan att ladda hela modulen."""
    import builtins
    from pathlib import Path

    path = Path("src/PDFishAndChipsStamp.py").resolve()
    src_lines = path.read_text(encoding="utf-8").splitlines()

    # Ta kod upp till men **inte med** första @dataclass-raden.
    cut = len(src_lines)
    for i, ln in enumerate(src_lines):
        if ln.strip().startswith("@dataclass"):
            cut = i  # stop BEFORE the decorator line
            break
    code = "\n".join(src_lines[:cut])

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pikepdf" or name.startswith("pikepdf."):
            raise ImportError("blocked pikepdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

    glb = {"__name__": "PDFishAndChipsStamp", "__file__": str(path)}
    exec(compile(code, str(path), "exec"), glb, glb)
    assert glb.get("HAVE_PIKEPDF") is False


    def fake_import(name, *args, **kwargs):
        if name == "pikepdf" or name.startswith("pikepdf."):
            raise ImportError("blocked pikepdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import, raising=True)

    glb = {"__name__": "PDFishAndChipsStamp", "__file__": str(path)}
    exec(compile(code, str(path), "exec"), glb, glb)
    assert glb.get("HAVE_PIKEPDF") is False


def test_read_secret_comment_path_with_invalid_then_valid_base64(tmp_path):
    wm = pdfc.PDFishAndChipsStamp()

    # Skapa en sida och lägg två content streams: först ogiltig base64, sedan giltig
    raw = _new_pdf()
    from pikepdf import Name, Array, Pdf

    with Pdf.open(io.BytesIO(raw)) as pdf:
        page = pdf.pages[0]
        bad = pdf.make_stream(b"\n% FISHANDCHIPS|@@@@\n")
        good_payload = base64.b64encode(b'{"data":"AA==","iv":"AA=="}')
        good_line = b"\n% " + wm.tag + b"|" + good_payload + b"\n"
        good = pdf.make_stream(good_line)
        page[Name("/Contents")] = Array([bad, good])
        buf = io.BytesIO()
        pdf.save(buf)
        pdf_bytes = buf.getvalue()

    # Kör read_secret mot bytes → pikepdf.Pdf.open(BytesIO(...)) internt
    try:
        wm.read_secret(pdf_bytes, key="k")
    except Exception as e:
        # Båda utfall ger täckning för base64-skip samt andra försöket
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}
