# tests/test_upload_basic.py
def test_upload_sample_pdf_fixture(upload_sample_pdf):
    r = upload_sample_pdf
    assert r.status_code in (200, 201, 202)
    js = r.get_json() or {}
    assert any(k in js for k in ("id","document_id"))

