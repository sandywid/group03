# tests/test_idempotency_and_duplicates.py
from io import BytesIO

def test_duplicate_upload_behavior(client, auth_headers, tiny_valid_pdf_bytes):
    # använd tillåtet filnamn (punkt är ok, underscore INTE)
    filename = "same.name.pdf"

    r1 = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data={"file": (BytesIO(tiny_valid_pdf_bytes.getvalue()), filename)},
        content_type="multipart/form-data",
    )
    r2 = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data={"file": (BytesIO(tiny_valid_pdf_bytes.getvalue()), filename)},
        content_type="multipart/form-data",
    )

    assert r1.status_code in (200, 201, 202)
    assert r2.status_code in (200, 201, 202, 409)
