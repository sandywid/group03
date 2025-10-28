# test/test_adnaswm_finish_last.py
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject

from AdnasWM import CommentStamp


def test__get_content_stream_objects_contents_is_not_stream_nor_array():
    """
    /Contents är satt till ett icke-stream-objekt (NameObject) → _get_content_stream_objects
    ska returnera tom lista och add_watermark ska därför kasta när den inte hittar en stream.
    Detta täcker den sista grenen 126->128 i AdnasWM.py.
    """
    # Skapa PDF där /Contents är t.ex. ett namnobjekt (inte stream/array)
    w = PdfWriter()
    page = w.add_blank_page(300, 300)
    page[NameObject("/Contents")] = NameObject("/NotAStream")
    buf = io.BytesIO()
    w.write(buf)
    pdf_in = buf.getvalue()

    wm = CommentStamp()
    with pytest.raises(Exception):
        wm.add_watermark(pdf_in, "s", "k")
