# test/test_watermark_defensive.py
import io

def test_get_version_public_does_not_return_secret(client, auth_headers):
    # create doc + version via known API
    r = client.post("/api/upload-document", headers=auth_headers, data={"file": (io.BytesIO(b"%PDF-1.4\n%EOF\n"), "w.pdf"), "name":"w.pdf"}, content_type="multipart/form-data")
    doc = r.get_json()
    methods = client.get("/api/get-watermarking-methods").get_json()["methods"]
    method = methods[0]["name"]
    r2 = client.post(f"/api/create-watermark/{doc['id']}", headers=auth_headers, json={"method":method, "position":None, "key":"k","secret":"s","intended_for":"a@x"})
    assert r2.status_code in (200,201)
    wm = r2.get_json()
    # public get-version by link should return PDF bytes, and must NOT include secrets in headers or body
    r3 = client.get(f"/api/get-version/{wm['link']}")
    assert r3.status_code == 200
    # ensure response body is PDF and not JSON containing secret
    assert r3.data.startswith(b"%PDF")
    assert b"secret" not in r3.data

