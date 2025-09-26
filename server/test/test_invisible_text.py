import io
import pytest
import fitz

from methods.invisible_text import InvisibleTextWatermark


def make_pdf():
    """Create a simple single-page PDF in memory for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_roundtrip():
    """Ensure a secret survives embed → extract."""
    pdf = make_pdf()
    m = InvisibleTextWatermark()
    key = "k123"
    secret = "unit-test-secret"

    out = m.add_watermark(pdf, secret=secret, key=key, position="center")
    recovered = m.read_secret(out, key=key)

    assert recovered == secret


def test_wrong_key():
    """Ensure using the wrong key raises an error."""
    pdf = make_pdf()
    m = InvisibleTextWatermark()
    out = m.add_watermark(pdf, secret="s", key="k1")

    with pytest.raises(Exception):
        m.read_secret(out, key="k2")


def test_applicability_always_true():
    """Check is_watermark_applicable always returns True for now."""
    pdf = make_pdf()
    m = InvisibleTextWatermark()
    assert m.is_watermark_applicable(pdf)
