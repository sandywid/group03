# test/test_logging_audit.py
import io
import logging
import time

def _try_upload_trigger(client, headers, name, content_bytes):
    """
    Hjälp: försök ladda upp en fil via offentligt dokument-endpoint.
    Vi använder content_type multipart/form-data så det triggar normal upload-logik.
    """
    pdf = io.BytesIO(content_bytes)
    data = {"file": (pdf, name), "name": name}
    return client.post(
        "/api/upload-document",
        headers=headers,
        data=data,
        content_type="multipart/form-data",
    )

def test_suspicious_write_requests_with_flag_are_logged(client, auth_headers, caplog):
    """
    Testa att skrivförsök som innehåller 'flag' triggar flag-detektionens loggning.
    Vi testar både 'name' och filinnehåll som bärare av ordet 'flag'.
    """

    # Fånga alla warning+loggar från root logger och app-loggers
    with caplog.at_level(logging.WARNING):
        # 1) Försök: name innehåller 'flag'
        r1 = _try_upload_trigger(client, auth_headers, name="report_with_flag.pdf", content_bytes=b"dummy")
        # 2) Försök: filinnehåll innehåller en FLAG-liknande token
        r2 = _try_upload_trigger(client, auth_headers, name="innocent.pdf", content_bytes=b"THIS IS A FLAG{secret}")

        # Låt loggsystemet få tid att flush:a (väldigt kort)
        time.sleep(0.05)

    # Sätt ihop fångade loggmeddelanden
    logs = "\n".join(rec.getMessage() for rec in caplog.records).lower()

    # Sanity: uploads borde inte crasha testmiljön (kan vara 200/201 eller 4xx beroende på auth)
    assert r1.status_code < 500, f"Upload request 1 gav serverfel: {r1.status_code} {r1.get_data(as_text=True)}"
    assert r2.status_code < 500, f"Upload request 2 gav serverfel: {r2.status_code} {r2.get_data(as_text=True)}"

    # Huvudkontroll: loggutdata måste nämna 'flag' eller någon annan känd indikator
    # (anpassa detta om er flag_detection.loggar ett annat ord)
    if not logs.strip():
        # Inget fångat — ge en tydlig felbeskrivning
        raise AssertionError(
            "Inga WARNING-loggar fångades. Kontrollera att flag_detection loggar vid skrivförsök med 'flag'. "
            f"Status r1={r1.status_code}, r2={r2.status_code}"
        )

    assert ("flag" in logs) or ("suspicious" in logs) or ("important" in logs) or ("attempt" in logs), (
        "Loggar fångades men innehöll inte förväntade nyckelord (flag/suspicious/important/attempt).\n"
        f"Captured logs:\n{logs}"
    )
