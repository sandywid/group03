# test/test_public_endpoints.py
from server import app

def test_healthz_json_and_200():
    c = app.test_client()
    r = c.get("/healthz")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)
    assert "message" in data  # servern har detta fält enligt er kod
    assert "db_connected" in data  # används för att gate:a integrations-tester

def test_get_watermarking_methods_shape():
    c = app.test_client()
    r = c.get("/api/get-watermarking-methods")
    assert r.status_code == 200
    js = r.get_json()
    assert "methods" in js and "count" in js
    assert js["count"] == len(js["methods"])
    # varje metod ska ha name + description (från WM-registret)
    for m in js["methods"]:
        assert "name" in m and "description" in m
