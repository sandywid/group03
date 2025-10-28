import io
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf

from PDFishAndChipsStamp import (
    PDFishAndChipsStamp,
    SecretNotFoundError,
    InvalidKeyError,
    WatermarkingError,
)


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_read_secret_requires_key():
    wm = PDFishAndChipsStamp()
    with pytest.raises(ValueError):
        wm.read_secret(_new_pdf(), key="")


def test_newstyle_missing_in_pdf():
    wm = PDFishAndChipsStamp()
    with pytest.raises(WatermarkingError):
        wm.add_watermark(out_pdf="x.pdf", payload=b"d")  # saknar in_pdf


def test_newstyle_missing_payload(tmp_path):
    wm = PDFishAndChipsStamp()
    in_path = tmp_path / "in.pdf"
    in_path.write_bytes(_new_pdf())
    with pytest.raises(WatermarkingError):
        wm.add_watermark(in_pdf=str(in_path))  # saknar payload


def test_newstyle_all_pages_false_only_first_touched(tmp_path):
    wm = PDFishAndChipsStamp()
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    in_path.write_bytes(_new_pdf(pages=3))

    res = wm.add_watermark(
        in_pdf=str(in_path),
        out_pdf=str(out_path),
        payload=b"xx",
        all_pages=False,
    )
    assert res.pages_streamed == 1
    assert out_path.exists() and out_path.stat().st_size > 0

    # Verifiera att BARA första sidan har taggen
    with Pdf.open(str(out_path)) as pdf:
        def page_has_tag(p):
            contents = p.get("/Contents")
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

        assert page_has_tag(pdf.pages[0]) is True
        # Övriga sidor ska vara orörda
        for i in range(1, len(pdf.pages)):
            assert page_has_tag(pdf.pages[i]) is False

def test_read_secret_no_watermark_raises(tmp_path):
    # PDF utan watermark ska ge SecretNotFoundError
    p = tmp_path / "plain.pdf"
    p.write_bytes(_new_pdf())
    wm = PDFishAndChipsStamp()
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(str(p), key="k")


def test_legacy_invalid_key_still_covered():
    # Redan täckt i dina tidigare tester, men vi upprepar för branch-täckning
    wm = PDFishAndChipsStamp()
    pdf = _new_pdf()
    out = wm.add_watermark(pdf, "secret", "right")
    with pytest.raises(InvalidKeyError):
        wm.read_secret(out, "wrong")

