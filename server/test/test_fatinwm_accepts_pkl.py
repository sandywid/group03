# test/test_fatinwm_accepts_pkl.py
import pickle
import importlib
from pathlib import Path

def _mod():
    return importlib.import_module("src.fatinWM")

def test_pkl_file_is_treated_as_pdf(tmp_path):
    FatinWM = _mod().FatinWM
    wm = FatinWM()

    # Skapa en fejk .pkl-fil
    data = {"model": [1, 2, 3]}
    pkl_path = tmp_path / "fake_model.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump(data, f)

    # Läs in den som bytes
    pkl_bytes = pkl_path.read_bytes()

    # Skicka in som bytes → inte sträng → return True enligt nuvarande logik
    result_bytes = wm.is_watermark_applicable(pkl_bytes)
    # Skicka in som fileobjekt → också True
    with open(pkl_path, "rb") as f:
        result_file = wm.is_watermark_applicable(f)

    # Skicka in som sträng (filnamn) → False, eftersom den slutar på .pkl
    result_str = wm.is_watermark_applicable(str(pkl_path))

    print("bytes:", result_bytes, " fileobj:", result_file, " str:", result_str)

    assert result_bytes is True
    assert result_file is True
    assert result_str is False

