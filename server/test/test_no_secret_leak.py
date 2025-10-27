# test/test_no_secret_leak.py
def test_versions_and_document_responses_do_not_contain_secrets(client, auth_headers, upload_sample_pdf):
    r = upload_sample_pdf
    resp_json = r.get_json()
    assert "secret" not in resp_json
    # list versions and ensure secret not present in list response
    doc_id = resp_json["id"]
    r2 = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
    assert r2.status_code == 200
    for v in r2.get_json().get("versions", []):
        assert "secret" not in v

