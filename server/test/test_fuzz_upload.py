# Added this for the fuzzing specialization task /Adna
# server/test/test_fuzz_upload.py
import io
import pytest
from hypothesis import given, strategies as st
from hypothesis import settings, HealthCheck

# Reuse fixtures from conftest
pytestmark = [pytest.mark.usefixtures("require_db")]

# Strategies
@st.composite
def pdf_like(draw):
    """Mutated 'PDF-like' bytes to test header/mimetype-controls and robustness."""
    base = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
    kind = draw(st.integers(min_value=0, max_value=5))
    if kind == 0:
        return base
    if kind == 1:  # truncation
        n = draw(st.integers(min_value=0, max_value=len(base)))
        return base[:n]
    if kind == 2:  # garbage prefix before %PDF-
        prefix = draw(st.binary(min_size=0, max_size=64))
        return prefix + base
    if kind == 3:  # correct header, the rest is just junk
        tail = draw(st.binary(min_size=0, max_size=1024))
        return b"%PDF-" + tail
    if kind == 4:  # large/random bytes (stress)
        return draw(st.binary(min_size=0, max_size=256 * 1024))
    # kind == 5: tom fil
    return b""

name_chars = st.characters(
    whitelist_categories=("Ll", "Lu", "Nd"),
    whitelist_characters=list("._-ÅÄÖåäö"),
    min_codepoint=32, max_codepoint=0x10FFFF
)
name_strategy = st.text(name_chars, min_size=1, max_size=80).map(lambda s: (s + ".pdf") if not s.endswith(".pdf") else s)

# Hypothesis runs many case; Turn of some health-checks due to IO
@settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
          deadline=None, max_examples=60)
@given(content=pdf_like(), filename=name_strategy)
def test_upload_pdf_mutations(client, auth_headers, content, filename):
    """Fuzzes multipart-upload with mutated PDF and various filenames."""
    data = {
        "file": (io.BytesIO(content), filename),
        "name": filename
    }
    r = client.post(
        "/api/upload-document",
        headers=auth_headers,
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    # Base rule: server shall not crash (500). Either 2xx (accepted) or 4xx (correct rejection).
    assert r.status_code < 500, f"Server crashed: {r.status_code} {r.get_data(as_text=True)[:300]}"
