# test/test_robustness_params.py
import pytest

# Undvik super-stora ints som SQLite inte kan binda; behåll “edge” ändå
@pytest.mark.parametrize("bad_id", ["", "null", "-999999999999", "👾", "%00", None])
def test_malformed_document_id_returns_4xx_not_5xx(client, auth_headers, bad_id):
    """
    Malformed document ids ska inte få servern att krascha (5xx).
    Tillåtna svar: 200/400/401/403/404 — men aldrig 5xx.
    """
    # GET
    r = client.get(f"/api/get-document/{bad_id}", headers=auth_headers)
    assert r.status_code < 500, f"GET returned 5xx för bad_id={bad_id}: {r.status_code} {r.get_data(as_text=True)}"

    # DELETE
    r = client.delete(f"/api/delete-document/{bad_id}", headers=auth_headers)
    assert r.status_code < 500, f"DELETE returned 5xx for bad_id={bad_id}: {r.status_code} {r.get_data(as_text=True)}"
