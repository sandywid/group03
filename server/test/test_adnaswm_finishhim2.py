# test/test_adnaswm_finishhim2.py
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject

from AdnasWM import CommentStamp, WatermarkingError, SecretNotFoundError


def _pdf_single_stream(data: bytes = b"q\nQ\n") -> bytes:
    w = PdfWriter()
    page = w.add_blank_page(300, 300)
    s = StreamObject(); s._data = data
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = s_ref  # <- singel stream (inte array)
    buf = io.BytesIO(); w.write(buf)
    return buf.getvalue()


def test__get_content_stream_objects_single_stream_hits_true_branch():
    # Träffar 126->128 (singel-stream-vägen)
    wm = CommentStamp()
    pdf = _pdf_single_stream()
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    page = reader.pages[0]
    streams = wm._get_content_stream_objects(page)  # noqa: SLF001
    assert len(streams) == 1 and isinstance(streams[0], StreamObject)


def test_add_watermark_with_filelike_hits_166_and_replaces_ok():
    # File-like (hasattr(read)) → täcker rad 166
    wm = CommentStamp()
    inp = io.BytesIO(_pdf_single_stream())
    out = wm.add_watermark(inp, "s", "k")
    assert isinstance(out, (bytes, bytearray)) and len(out) > 0


def test_add_watermark_stream_get_data_exception_hits_190_191(monkeypatch):
    # Tvinga get_data() att kasta → få WatermarkingError (rad 190–191)
    wm = CommentStamp()

    # Monkeypatcha klass-metoden så *det valda* stream-objektet kastar
    orig_get_data = StreamObject.get_data

    def boom(self):
        raise ValueError("boom")

    monkeypatch.setattr(StreamObject, "get_data", boom, raising=True)
    try:
        with pytest.raises(WatermarkingError):
            wm.add_watermark(_pdf_single_stream(), "s", "k")
    finally:
        # återställ för säkerhets skull
        monkeypatch.setattr(StreamObject, "get_data", orig_get_data, raising=True)


def test_read_secret_continue_on_get_data_exception_hits_222_223(monkeypatch):
    # Tvinga s.get_data() att kasta → 'except: continue' i loopen, leder till SecretNotFoundError
    wm = CommentStamp()
    pdf = _pdf_single_stream()

    orig_get_data = StreamObject.get_data

    def boom(self):
        raise RuntimeError("nope")

    monkeypatch.setattr(StreamObject, "get_data", boom, raising=True)
    try:
        with pytest.raises(SecretNotFoundError):
            wm.read_secret(pdf, key="k")
    finally:
        monkeypatch.setattr(StreamObject, "get_data", orig_get_data, raising=True)
