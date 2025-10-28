# test/test_watermarking_utils_finishhim.py
import sys
import types
import importlib
from pathlib import Path

import pytest
from pypdf import PdfWriter


def _pdf_bytes(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


import io  # efter hjälpfunktionen


def test_get_method_passthrough_instance():
    """Träffar rad 89: get_method med redan-instans → returnera samma."""
    utils = importlib.import_module("watermarking_utils")
    # hämta valfri registrerad metod och passera instansen
    any_method = next(iter(utils.METHODS.values()))
    assert utils.get_method(any_method) is any_method


def test_explore_pdf_with_fitz_xref_object_raises_hits_198_199(monkeypatch, tmp_path):
    """
    Injicera ett fejk-fitZ som
      - har 0 sidor,
      - xref_length>1,
      - xref_object kastar → except-grenen 198–199,
      - xref_is_stream returnerar False.
    """
    utils = importlib.import_module("watermarking_utils")

    class FakeDoc:
        page_count = 0
        def xref_length(self): return 3
        def xref_object(self, xref, compressed=False):  # kastar ibland
            raise RuntimeError("boom")
        def xref_is_stream(self, xref): return False
        def close(self): pass

    class FakeFitz(types.SimpleNamespace):
        def open(self, stream, filetype): return FakeDoc()

    monkeypatch.setitem(sys.modules, "fitz", FakeFitz())

    pdf_path = tmp_path / "in.pdf"
    # enkel PDF
    w = PdfWriter(); w.add_blank_page(200, 200)
    b = io.BytesIO(); w.write(b); pdf_path.write_bytes(b.getvalue())

    tree = utils.explore_pdf(str(pdf_path))
    assert tree["type"] == "Document"
    # bör finnas någon "obj:"-nod tillagd via xref-loopen (även om content_sha1=None)
    assert any(n.get("id", "").startswith("obj:") for n in tree.get("children", []))


def test_explore_pdf_fallback_regex_hits_215_252(monkeypatch, tmp_path):
    """
    Låt import fitz lyckas men fitz.open kasta → except → regex-fallback (215–252).
    """
    utils = importlib.import_module("watermarking_utils")

    class FakeFitz(types.SimpleNamespace):
        def open(self, *a, **k): raise RuntimeError("open-fail")

    monkeypatch.setitem(sys.modules, "fitz", FakeFitz())

    pdf_path = tmp_path / "in2.pdf"
    w = PdfWriter(); w.add_blank_page(200, 200)
    b = io.BytesIO(); w.write(b); pdf_path.write_bytes(b.getvalue())

    tree = utils.explore_pdf(str(pdf_path))
    # fallback lägger "page:"-noder + "obj:"-noder
    assert tree["type"] == "Document"
    assert any(c.get("id", "").startswith(("obj:", "page:")) for c in tree.get("children", []))
