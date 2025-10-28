# test/test_adnaswm_finishhim.py
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject, ArrayObject

from AdnasWM import CommentStamp, SecretNotFoundError


def _pdf_bytes_with_single_stream(data: bytes = b"q\nQ\n") -> bytes:
    w = PdfWriter()
    page = w.add_blank_page(300, 300)
    s = StreamObject(); s._data = data
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = s_ref
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def test_add_watermark_empty_contents_array_raises():
    """
    Täck grenen där /Contents är en tom ArrayObject → ingen stream att skriva till.
    (träffar 126->128 i AdnasWM.py)
    """
    w = PdfWriter()
    page = w.add_blank_page(300, 300)
    page[NameObject("/Contents")] = ArrayObject([])  # tom array
    buf = io.BytesIO(); w.write(buf)
    pdf_in = buf.getvalue()

    wm = CommentStamp()
    with pytest.raises(Exception):
        wm.add_watermark(pdf_in, "s", "k")


def test_read_secret_on_path_without_wm_triggers_close(tmp_path):
    """
    Kör read_secret() mot en *sökväg* (inte bytes/filelike) som saknar watermark.
    Detta passerar öppning/avslut (doc.close) i finally-blocket.
    (träffar ~190–191 & 215 i AdnasWM.py)
    """
    p = tmp_path / "plain.pdf"
    p.write_bytes(_pdf_bytes_with_single_stream(b"q\nQ\n"))

    wm = CommentStamp()
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(str(p), key="k")


def test_read_secret_continue_on_invalid_base64_then_not_found():
    """
    För in en kommentar med felaktig base64 → b64decode fel → continue-vägen i loopen.
    Ingen giltig tagg efter det → SecretNotFoundError.
    (träffar ~222–223 i AdnasWM.py)
    """
    bad_line = b"% LCPWM1|@@@@\n"  # '@@@@' är ogiltig base64
    pdf_in = _pdf_bytes_with_single_stream(b"q\nQ\n" + bad_line)

    wm = CommentStamp()
    with pytest.raises(SecretNotFoundError):
        wm.read_secret(pdf_in, key="k")
