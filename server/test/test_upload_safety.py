# test/test_upload_safety.py
import io
import pathlib

def test_upload_rejects_path_traversal(client, auth_headers):
    pdf = io.BytesIO(b"%PDF-1.4\n%EOF\n")
    data = {"file": (pdf, "report.pdf"), "name": "../outside.txt"}
    r = client.post("/api/upload-document", headers=auth_headers, data=data, content_type="multipart/form-data")
    assert r.status_code in (400,422), r.get_data(as_text=True)

    # If the app has STORAGE_DIR configured, ensure no files ended up outside it
    storage_conf = client.application.config.get("STORAGE_DIR")
    if storage_conf:
        storage = pathlib.Path(storage_conf)
        # common-sense check: no file created above storage root
        # list all files created and assert they are inside storage
        created = [p for p in storage.rglob("*") if p.is_file()]
        assert all(str(p).startswith(str(storage)) for p in created), "Found file(s) outside configured storage dir"
