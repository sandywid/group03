# test/test_adnaswm_micro.py
import io
import importlib.util
import sys
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject, StreamObject, ArrayObject, IndirectObject

import AdnasWM as ad


def _pdf_with_contents_array_mixed() -> bytes:
    """/Contents = Array[ stream, non-stream ] så att 'isinstance(s, StreamObject)' blir både True/False."""
    w = PdfWriter()
    page = w.add_blank_page(300, 300)
    s = StreamObject()
    s._data = b"q\nQ\n"
    s_ref = w._add_object(s)
    page[NameObject("/Contents")] = ArrayObject([s_ref, NameObject("/NotAStream")])
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _pdf_single_stream() -> bytes:
    w = PdfWriter()
    p = w.add_blank_page(300, 300)
    s = StreamObject()
    s._data = b"q\nQ\n"
    s_ref = w._add_object(s)
    p[NameObject("/Contents")] = s_ref
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_is_watermark_applicable_hits_true_branch():
    wm = ad.CommentStamp()
    assert wm.is_watermark_applicable(None) is True  # rad ~154


def test_get_content_stream_objects_array_has_non_stream_branch(monkeypatch):
    wm = ad.CommentStamp()
    pdf = _pdf_with_contents_array_mixed()
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    page = reader.pages[0]
    streams = wm._get_content_stream_objects(page)  # noqa: SLF001
    # Minst en stream ska hittas (första), andra ska ignoreras
    assert streams and all(isinstance(s, StreamObject) for s in streams)


def test_read_secret_continue_on_get_data_exception(monkeypatch):
    wm = ad.CommentStamp()
    pdf = _pdf_single_stream()

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    page = reader.pages[0]
    contents = page.get("/Contents")
    stream_obj = contents.get_object() if isinstance(contents, IndirectObject) else contents

    def boom():
        raise ValueError("kaboom")

    monkeypatch.setattr(stream_obj, "get_data", boom, raising=True)
    with pytest.raises(ad.SecretNotFoundError):
        wm.read_secret(pdf, key="k")  # träffar continue-vägen och slutar i not-found


def test_decrypt_payload_missing_fields_branch():
    wm = ad.CommentStamp()
    # Bygg en WM-blob: MAGIC + len + JSON (saknar fält → InvalidKeyError-grenen)
    json_bytes = b'{"enc": false}'
    blob = wm._MAGIC + len(json_bytes).to_bytes(4, "big") + json_bytes
    with pytest.raises(ad.InvalidKeyError):
        wm._decrypt_payload(blob, "k")  # noqa: SLF001


def test_module_reload_without_cryptography_triggers_AESGCM_None_and_enc_guard(monkeypatch, tmp_path):
    """Träffar AESGCM-import-fallback och enc=True-guard."""
    for m in [
        "cryptography",
        "cryptography.hazmat",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.ciphers",
        "cryptography.hazmat.primitives.ciphers.aead",
    ]:
        sys.modules.pop(m, None)

    class Blocker:
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith("cryptography.hazmat.primitives.ciphers.aead"):
                raise ModuleNotFoundError("blocked cryptography for test")
            return None

    sys.meta_path.insert(0, Blocker())
    try:
        src_path = Path("src/AdnasWM.py").resolve()
        spec = importlib.util.spec_from_file_location("AdnasWM_noaes", str(src_path))
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)

        assert mod.AESGCM is None  # import-fallback träffad

        # enc=True → ska slå på enc-guard. Lägg på MAGIC + len + JSON.
        json_bytes = b'{"enc": true, "iv":"AA==","data":"AA=="}'
        blob = mod.CommentStamp()._MAGIC + len(json_bytes).to_bytes(4, "big") + json_bytes
        with pytest.raises(mod.InvalidKeyError):
            mod.CommentStamp()._decrypt_payload(blob, "k")  # noqa: SLF001
    finally:
        sys.meta_path.pop(0)
