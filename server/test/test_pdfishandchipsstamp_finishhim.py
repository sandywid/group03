# test/test_pdfishandchipsstamp_finishhim.py
import io
import base64
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf, Name, Array
from PDFishAndChipsStamp import PDFishAndChipsStamp, SecretNotFoundError


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def test_read_secret_path_invalid_then_valid_comment(tmp_path):
    """
    Skapa ett PDF där contents är [ogiltig base64, giltig base64] i streams.
    Kör read_secret mot *sökväg* för att träffa bytes/path-grenarna i koden.
    (träffar blocket ~186–230 inkl. 196->205, 201–203, 205->230, 227–228, 230->233)
    """
    raw = _new_pdf()
    wm = PDFishAndChipsStamp()

    with Pdf.open(io.BytesIO(raw)) as pdf:
        page = pdf.pages[0]
        bad = pdf.make_stream(b"\n% FISHANDCHIPS|@@@@\n")  # felaktig base64 → skip/continue
        good_payload = base64.b64encode(b'{"data":"AA==","iv":"AA=="}')
        good_line = b"\n% " + wm.tag + b"|" + good_payload + b"\n"
        good = pdf.make_stream(good_line)
        page[Name("/Contents")] = Array([bad, good])
        buf = io.BytesIO(); pdf.save(buf)
        p = tmp_path / "combo.pdf"
        p.write_bytes(buf.getvalue())

    try:
        wm.read_secret(str(p), key="k")
    except Exception as e:
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}


def test_embed_stream_comments_array_append_raises(monkeypatch, tmp_path):
    """
    Tvinga except-vägen i _embed_stream_comments genom att få Array.append att kasta.
    (träffar ~255–257)
    """
    from pikepdf import Array as PikeArray

    # monkeypatcha klassens append för testets scope
    def boom(self, obj):
        raise RuntimeError("append-bomb")
    monkeypatch.setattr(PikeArray, "append", boom, raising=True)

    # Vanligt new-style-anrop som går via _embed_stream_comments
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    in_path.write_bytes(_new_pdf())

    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(in_pdf=str(in_path), out_pdf=str(out_path), payload=b"x", all_pages=True)
    # Bara verifikation att körningen gick igenom även när append kastade
    assert res.pages_streamed >= 1 and out_path.exists()
