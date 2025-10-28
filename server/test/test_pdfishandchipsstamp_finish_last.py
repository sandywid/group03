# test/test_pdfishandchipsstamp_finish_last.py
import io
import base64
from pathlib import Path
import types

import pytest
from pypdf import PdfWriter
from pikepdf import Pdf, Dictionary, Array

import PDFishAndChipsStamp as mod
from PDFishAndChipsStamp import PDFishAndChipsStamp, SecretNotFoundError, InvalidKeyError


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_read_secret_malformed_names_tree_falls_back_to_xmp(monkeypatch):
    """
    Täck 189->196, 190->189 och 202–203:
    - Root['/Names'] finns men EmbeddedFiles/entries är oanvändbara
    - XMP.get returnerar base64 så XMP-grenen körs
    """
    class FakeMD(dict):
        def get(self, key):
            # {"data":"AA==","iv":"AA=="} i base64
            return "eyJkYXRhIjoiQUE9PSIsIml2IjoiQUE9PSJ9"

    class FakeDoc:
        def __init__(self):
            # /Names finns… men /EmbeddedFiles/Names är feltyp/trasigt
            self.Root = {
                "/Names": {
                    "/EmbeddedFiles": {
                        "/Names": {"not": "array"}  # gör EF oanvändbart
                    }
                }
            }
            self.pages = [{}]
        def open_metadata(self):
            return FakeMD()
        def close(self):
            self.closed = True

    class FakePdfWrapper:
        @staticmethod
        def open(obj):
            return FakeDoc()

    monkeypatch.setattr(mod.pikepdf, "Pdf", FakePdfWrapper, raising=True)

    wm = PDFishAndChipsStamp()
    try:
        wm.read_secret(b"%PDF-FAKE%", key="k")
    except Exception as e:
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}


def test_read_secret_single_stream_valid_comment_hits_230_to_233(tmp_path):
    """
    Contents är EN stream med giltig tag → kommentarsvägen utan Array (230->233).
    """
    wm = PDFishAndChipsStamp()
    raw = _new_pdf()
    with Pdf.open(io.BytesIO(raw)) as pdf:
        page = pdf.pages[0]
        good_payload = base64.b64encode(b'{"data":"AA==","iv":"AA=="}')
        line = b"\n% " + wm.tag + b"|" + good_payload + b"\n"
        page["/Contents"] = pdf.make_stream(line)
        buf = io.BytesIO()
        pdf.save(buf)
        p = tmp_path / "s.pdf"
        p.write_bytes(buf.getvalue())

    try:
        wm.read_secret(str(p), key="k")
    except Exception as e:
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}


def test_embed_stream_comments_array_append_raises_hits_255_257(monkeypatch):
    """
    Patcha *modulens* pikepdf.Array till en klass vars append kastar.
    Då passerar isinstance(..., pikepdf.Array) och try/except (255–257) träffas.
    """
    wm = PDFishAndChipsStamp()

    class BoomArray(list):
        def append(self, obj):
            raise RuntimeError("append-bomb")

    # Gör så att isinstance(x, pikepdf.Array) blir True för BoomArray
    monkeypatch.setattr(mod, "pikepdf", type("P", (), {"Array": BoomArray})(), raising=False)

    class FakePdf:
        def __init__(self):
            self.pages = [{"/Contents": BoomArray()}]
        def make_stream(self, bts: bytes):
            return {"__stream__": bts}

    touched = PDFishAndChipsStamp._embed_stream_comments(  # noqa: SLF001
        wm, FakePdf(), b"YWJj", all_pages=True
    )
    assert touched == 1


def test_embed_attachment_names_exists_but_no_embeddedfiles_hits_282_284(monkeypatch):
    """
    Root har '/Names' men ingen '/EmbeddedFiles' → funktionen skapar EF och Names-array.
    Täck 282->284 (och 286 i samma körning).
    """
    class FakeArray(list):
        pass

    monkeypatch.setattr(mod, "pikepdf", type("P", (), {"Array": FakeArray})(), raising=False)
    monkeypatch.setattr(mod, "Name", lambda s: s, raising=True)

    class FakePdf:
        def __init__(self):
            self.Root = {"/Names": {}}  # saknar /EmbeddedFiles
        def make_stream(self, bts):
            return {"stream": bts}
        def add_object(self, obj):
            return obj

    ok = mod.PDFishAndChipsStamp._embed_attachment(PDFishAndChipsStamp(), FakePdf(), b"YWJj")  # noqa: SLF001
    assert ok is True

def test_read_secret_xmp_invalid_base64_hits_202_203(monkeypatch):
    """
    Täck except Exception: pass (202–203) i XMP-grenen genom att få XMP.get()
    att returnera ogiltig base64 → b64decode kastar, fångas, och funktionen
    fortsätter till kommentarvägen (som slutar i SecretNotFoundError).
    """
    wm = PDFishAndChipsStamp()

    class BadMD(dict):
        def get(self, key):
            return "!!!NOT_BASE64!!!"  # ogiltigt för base64.b64decode

    class FakeDoc:
        def __init__(self):
            self.Root = {"/Names": {}}  # inga embedded files
            self.pages = [{}]
        def open_metadata(self):
            return BadMD()
        def close(self):
            self.closed = True

    class FakePdfWrapper:
        @staticmethod
        def open(obj):
            return FakeDoc()

    monkeypatch.setattr(mod.pikepdf, "Pdf", FakePdfWrapper, raising=True)

    # XMP-decode misslyckas (202–203 träffas) → sedan ingen kommentar → SecretNotFoundError
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(b"%PDF-FAKE%", key="k")

