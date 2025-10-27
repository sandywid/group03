# tests/test_upload_basic.py
def test_upload_sample_pdf_fixture(upload_sample_pdf):
    js = upload_sample_pdf
    assert isinstance(js, dict)
    assert js.get("status", "ok") in ("ok", "uploaded", "processed")
    assert any(k in js for k in ("id", "document_id"))

