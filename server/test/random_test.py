import io
import pytest

def test_missing_file(client):
    r = client.post("/api/watermark", data={"secret":"s","key":"k"})
    assert r.status_code in (400, 422)

def test_wrong_mimetype(client):
    r = client.post(
        "/api/watermark",
        data={"secret":"s","key":"k","file":(io.BytesIO(b"X"),"note.txt")},
        content_type="multipart/form-data",
    )
    assert r.status_code in (400, 415)

