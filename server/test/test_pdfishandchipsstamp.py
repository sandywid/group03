import io
import pytest

pikepdf = pytest.importorskip("pikepdf")
from pikepdf import Pdf

from PDFishAndChipsStamp import (
    PDFishAndChipsStamp,
    SecretNotFoundError,
    InvalidKeyError,
)

# Create a minimal PDF with pypdf (stable over versions)
from pypdf import PdfWriter


def _new_pdf(pages: int = 1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_legacy_roundtrip_bytes_in_and_out():
    pdf_in = _new_pdf(pages=1)
    wm = PDFishAndChipsStamp()

    secret = "lakehouse"
    key = "trout-key"

    # Legacy-API: bytes in and bytes out
    pdf_out = wm.add_watermark(pdf_in, secret, key)
    assert isinstance(pdf_out, (bytes, bytearray)) and len(pdf_out) >= len(pdf_in)

    recovered = wm.read_secret(pdf_out, key)
    assert recovered == secret


def test_legacy_invalid_key_raises():
    pdf_in = _new_pdf()
    wm = PDFishAndChipsStamp()
    out = wm.add_watermark(pdf_in, "alpha", "good-key")

    with pytest.raises(InvalidKeyError):
        wm.read_secret(out, key="bad-key")


def test_missing_secret_or_key_raises_valueerror():
    pdf_in = _new_pdf()
    wm = PDFishAndChipsStamp()
    # Use positional argument to safely end up in legacy path
    with pytest.raises(ValueError):
        wm.add_watermark(pdf_in, "", "k")
    with pytest.raises(ValueError):
        wm.add_watermark(pdf_in, "s", "")


def test_read_secret_no_wm_raises():
    wm = PDFishAndChipsStamp()
    with Pdf.open(io.BytesIO(_new_pdf())) as pdf:
        buf = io.BytesIO()
        pdf.save(buf)
        raw_pdf = buf.getvalue()

    with pytest.raises(SecretNotFoundError):
        wm.read_secret(raw_pdf, key="any")


def test_newstyle_roundtrip_writes_everything(tmp_path):
    # Arrange
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    with open(in_path, "wb") as f:
        f.write(_new_pdf(pages=3))

    payload = b"payload-blob-42"
    wm = PDFishAndChipsStamp()

    # Act: New style (file in/out) should write to out_path and return Result
    res = wm.add_watermark(
        in_pdf=str(in_path),
        out_pdf=str(out_path),
        payload=payload,
        all_pages=True,
    )

    assert res.pages_streamed == 3
    # Flaggarna kan vara False beroende på build/lib, men de ska åtminstone vara bools
    assert isinstance(res.xmp_ok, bool)
    assert isinstance(res.attachment_ok, bool)
    assert out_path.exists() and out_path.stat().st_size > 0

    # Verify 1: kommentaretikett i första sidans innehåll
    with Pdf.open(str(out_path)) as pdf:
        page0 = pdf.pages[0]
        contents = page0.get("/Contents")
        if contents is None:
            raise AssertionError("Expected /Contents after watermarking")

        # contents kan vara stream eller array av streams
        try:
            from pikepdf import Array  # type: ignore
            is_array = isinstance(contents, Array)
        except Exception:
            is_array = False

        if is_array:
            streams = [bytes(s.read_bytes()) for s in contents]
        else:
            streams = [bytes(contents.read_bytes())]

        assert any(b"% FISHANDCHIPS|" in b for b in streams)

        # Verify 2: inbäddad fil finns (filnamn varierar → bara existenskoll)
        if res.attachment_ok:
            names = pdf.Root.get("/Names")
            assert names is not None
            ef = names.get("/EmbeddedFiles")
            assert ef is not None
            arr = list(ef.get("/Names", []))
            # Structure: [filename1, filespec1, filename2, filespec2, ...]
            assert len(arr) >= 2
        else:
            pass

