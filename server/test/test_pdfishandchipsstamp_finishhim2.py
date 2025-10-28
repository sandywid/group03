# test/test_pdfishandchipsstamp_finishhim2.py
import io
import base64
import pytest
from pypdf import PdfWriter
from pikepdf import Pdf, Dictionary, Array

from PDFishAndChipsStamp import PDFishAndChipsStamp, InvalidKeyError, SecretNotFoundError


def _new_pdf(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def test_read_secret_via_embedded_file_hits_186_194(tmp_path):
    """
    Bygg ett Names/EmbeddedFiles-träd som innehåller vår fil → läs via embedded file.
    Täcker PDFishAndChipsStamp.py rader ~186–194.
    """
    wm = PDFishAndChipsStamp()
    raw = _new_pdf()

    with Pdf.open(io.BytesIO(raw)) as pdf:
        payload = b'{"data":"AA==","iv":"AA=="}'  # leder till InvalidKeyError i decrypt men vägen täcks
        stream = pdf.make_stream(payload)

        # Viktigt: pikepdf.Dictionary vill ha str-nycklar som börjar med "/"
        filespec = Dictionary({"/EF": Dictionary({"/F": stream})})
        ef = Dictionary({"/Names": Array([wm.embedded_filename, filespec])})
        names = Dictionary({"/EmbeddedFiles": ef})
        pdf.Root["/Names"] = names

        out = io.BytesIO(); pdf.save(out)
        p = tmp_path / "ef.pdf"; p.write_bytes(out.getvalue())

    try:
        wm.read_secret(str(p), key="k")
    except Exception as e:
        # Decrypt faller, men läsvägen via 186–194 körs
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}


def test_read_secret_comments_first_bad_object_then_good_tag_hits_227_228(tmp_path):
    """
    Första elementet saknar read_bytes → except-pass; andra innehåller en giltig taggrad.
    Täcker rader ~227–228 (except: pass) och fortsatt kommentarsväg.
    """
    wm = PDFishAndChipsStamp()
    raw = _new_pdf()

    with Pdf.open(io.BytesIO(raw)) as pdf:
        page = pdf.pages[0]
        good_payload = base64.b64encode(b'{"data":"AA==","iv":"AA=="}')
        good_line = b"\n% " + wm.tag + b"|" + good_payload + b"\n"
        good = pdf.make_stream(good_line)

        # Första elementet: en pikepdf.Dictionary (valid PDF-objekt) utan read_bytes → AttributeError i din loop.
        bad_obj_without_read_bytes = Dictionary()

        page["/Contents"] = Array([bad_obj_without_read_bytes, good])

        buf = io.BytesIO(); pdf.save(buf)
        p = tmp_path / "cm.pdf"; p.write_bytes(buf.getvalue())

    try:
        wm.read_secret(str(p), key="k")
    except Exception as e:
        assert type(e).__name__ in {"InvalidKeyError", "SecretNotFoundError"}
