import importlib
import PDFishAndChipsStamp as pdfc
import pytest

def test_pdfishandchipsstamp_init_requires_pikepdf(monkeypatch):
    # Sätt flaggan som modulen satte vid import
    monkeypatch.setattr(pdfc, "HAVE_PIKEPDF", False, raising=True)
    with pytest.raises(ModuleNotFoundError):
        pdfc.PDFishAndChipsStamp()

def test_pdfishandchipsstamp_usage_and_applicable():
    # De här raderna brukar vara omärkta → enkel körning ger täckning
    assert isinstance(pdfc.PDFishAndChipsStamp.get_usage(), str)
    # is_watermark_applicable returnerar alltid True i din kod
    # Kör den explicit så raden räknas i coverage.
    wm = pdfc.PDFishAndChipsStamp()  # funkar eftersom pikepdf finns i din miljö
    assert wm.is_watermark_applicable(None) is True
