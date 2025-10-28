# test/test_pdfishandchipsstamp_lastbits.py
import io
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf, Dictionary, Array

from PDFishAndChipsStamp import PDFishAndChipsStamp


def _new_pdf(pages=1) -> bytes:
    """Create a simple valid PDF with pypdf that pikepdf can open/edit."""
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_legacy_via_kwargs_wrapper_path():
    """Exercise legacy wrapper path by passing kwargs (pdf/secret/key)."""
    wm = PDFishAndChipsStamp()
    pdf_in = _new_pdf()
    out = wm.add_watermark(pdf=pdf_in, secret="s", key="k")
    assert isinstance(out, (bytes, bytearray)) and len(out) >= len(pdf_in)


def test_newstyle_alias_input_destination_content(tmp_path):
    """Hit new-style alias names: input_pdf + destination + content."""
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    in_path.write_bytes(_new_pdf(pages=1))

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(
        input_pdf=str(in_path),    # alias for in_pdf
        destination=str(out_path), # alias for out_pdf
        content=b"xx",             # alias for payload
        all_pages=True,
    )
    assert res.pages_streamed == 1
    assert out_path.exists() and out_path.stat().st_size > 0


def test_newstyle_alias_payload_bytes_and_existing_names_tree(tmp_path):
    """
    Cover the path where /Root already has /Names with /EmbeddedFiles,
    and that EF dict already contains /Names as an Array([]).
    """
    in_path = tmp_path / "in_names.pdf"
    out_path = tmp_path / "out_names.pdf"

    # Start from a one-page PDF (pypdf), then edit with pikepdf
    raw = _new_pdf(pages=1)
    with Pdf.open(io.BytesIO(raw)) as pdf:
        # Build a Names tree: /Names { /EmbeddedFiles <ef> } and ef has /Names []
        ef = Dictionary({"/Names": Array([])})      # NOTE: use string keys, not Name(...)
        names = Dictionary({"/EmbeddedFiles": ef})  # direct reference, no add_object()
        pdf.Root["/Names"] = names                  # attach to catalog
        pdf.save(str(in_path))

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(
        in_pdf=str(in_path),
        out_pdf=str(out_path),
        payload_bytes=bytearray(b"hello"),  # alias + different buffer type
        all_pages=True,
    )
    assert res.pages_streamed >= 1
    assert out_path.exists() and out_path.stat().st_size > 0


def test_newstyle_alias_payload_bytes_names_is_not_array(tmp_path):
    """
    Cover the branch where ef['/Names'] is NOT an Array, so the code converts it.
    We store a stream at '/Names' to force the conversion path.
    """
    in_path = tmp_path / "in_names2.pdf"
    out_path = tmp_path / "out_names2.pdf"

    raw = _new_pdf(pages=1)
    with Pdf.open(io.BytesIO(raw)) as pdf:
        # /Names is *not* an Array (use a small stream) → code should convert it to an Array
        bad_ef = Dictionary({"/Names": pdf.make_stream(b"")})
        names = Dictionary({"/EmbeddedFiles": bad_ef})
        pdf.Root["/Names"] = names
        pdf.save(str(in_path))

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(
        in_pdf=str(in_path),
        out_pdf=str(out_path),
        payload_bytes=memoryview(b"world"),  # alias + different buffer type
        all_pages=True,
    )
    assert res.pages_streamed >= 1
    assert out_path.exists() and out_path.stat().st_size > 0
