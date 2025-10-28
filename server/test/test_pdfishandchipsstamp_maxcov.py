import io
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf
from PDFishAndChipsStamp import PDFishAndChipsStamp, WatermarkingError, InvalidKeyError


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def _page_has_tag(page) -> bool:
    contents = page.get("/Contents")
    if contents is None:
        return False
    try:
        from pikepdf import Array  # type: ignore
        is_array = isinstance(contents, Array)
    except Exception:
        is_array = False
    if is_array:
        streams = [bytes(s.read_bytes()) for s in contents]
    else:
        streams = [bytes(contents.read_bytes())]
    return any(b"% FISHANDCHIPS|" in b for b in streams)


def test_newstyle_alias_params_pdf_output_data_all_pages_true(tmp_path):
    # Täck alias: pdf=, output_pdf=, data=
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    in_path.write_bytes(_new_pdf(pages=2))

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(
        pdf=str(in_path),                 # alias för in_pdf
        output_pdf=str(out_path),         # alias för out_pdf
        data=b"payload-har-innehall",     # alias för payload
        all_pages=True,
    )
    assert res.pages_streamed == 2
    assert out_path.exists() and out_path.stat().st_size > 0

    with Pdf.open(str(out_path)) as pdf:
        assert _page_has_tag(pdf.pages[0]) is True
        assert _page_has_tag(pdf.pages[1]) is True


def test_newstyle_alias_src_dest_watermark_single_page(tmp_path):
    # Täck fler alias: src=, dest=, watermark=
    in_path = tmp_path / "in2.pdf"
    out_path = tmp_path / "out2.pdf"
    in_path.write_bytes(_new_pdf(pages=1))

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(
        src=str(in_path),
        dest=str(out_path),
        watermark=b"bytes-blob-here",
        all_pages=True,
    )
    assert res.pages_streamed == 1
    with Pdf.open(str(out_path)) as pdf:
        assert _page_has_tag(pdf.pages[0]) is True


def test_legacy_unicode_secret_and_wrong_key_path():
    # Täck legacy med unicode och InvalidKeyError-gren
    wm = PDFishAndChipsStamp()
    pdf = _new_pdf()
    out = wm.add_watermark(pdf, "🌊-sjöhemlis-🐟", "ratt-nyckel")
    with pytest.raises(InvalidKeyError):
        wm.read_secret(out, "fel-nyckel")
