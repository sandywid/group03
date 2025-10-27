def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.get_json()
    assert (
        body.get("status") in ("ok", "healthy")
        or ("message" in body and isinstance(body.get("db_connected"), bool))
    )
