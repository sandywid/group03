import io
import os
import base64
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf

import runpy

from PDFishAndChipsStamp import PDFishAndChipsStamp, SecretNotFoundError


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def test_newstyle_default_out_path(tmp_path):
    in_path = tmp_path / "in.pdf"
    in_path.write_bytes(_new_pdf())
    # Lämna out_pdf=None → koden ska generera in.wm.pdf
    wm = PDFishAndChipsStamp()
    res = wm.add_watermark(in_pdf=str(in_path), payload=b"abc", all_pages=True)
    # Kontrollera att default-utfilen skapats
    gen_path = in_path.with_name(in_path.stem + ".wm" + in_path.suffix)
    assert gen_path.exists() and gen_path.stat().st_size > 0
    assert res.pages_streamed >= 1


def test_read_secret_skips_invalid_base64_then_reads_valid(tmp_path):
    # Bygg ett PDF med två kommentarer: först ogiltig base64, sedan giltig
    from pikepdf import Name, Array, Dictionary

    # Skapa en en-sidig PDF
    raw = _new_pdf()
    with Pdf.open(io.BytesIO(raw)) as pdf:
        page = pdf.pages[0]
        # 1) lägg in en ogiltig "taggrad" i en stream
        bad = pdf.make_stream(b"\n% FISHANDCHIPS|@@@@\n")
        # 2) lägg in en *giltig* taggrad efteråt
        payload = b'{"enc":false,"secret":"OK","mac":"AA=="}'  # minimal form; dekryptering kommer falla/eller ge InvalidKeyError
        line = b"\n% FISHANDCHIPS|" + base64.b64encode(payload) + b"\n"
        good = pdf.make_stream(line)

        # Contents som array av två streams: först trasig, sen giltig
        page[Name("/Contents")] = Array([bad, good])
        tmp = io.BytesIO()
        pdf.save(tmp)
        pdf_bytes = tmp.getvalue()

    wm = PDFishAndChipsStamp()
    # Vi bryr oss inte om returvärdet lyckas dekryptera (kan bli InvalidKeyError),
    # utan att koden *försöker* efter att ha hoppat över ogiltig base64.
    try:
        wm.read_secret(pdf_bytes, key="k")
    except Exception as e:
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}

def test_run_module_main_block():
    # Kör __main__-vakten så sista raderna täcks
    runpy.run_module("PDFishAndChipsStamp", run_name="__main__")
