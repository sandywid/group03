# test/test_watermarking_utils.py
import io
import os
import importlib

import pytest

utils = importlib.import_module("watermarking_utils")


def test_module_imports_and_dunder_all_ok():
    # bara kontrollera att modulen laddas och att __all__ (om finns) pekar på faktiska objekt
    if hasattr(utils, "__all__"):
        for name in utils.__all__:
            assert hasattr(utils, name)


def test_basic_helpers_behave_reasonably(tmp_path, monkeypatch):
    # Dessa anropar är "best effort" – kör bara om de finns i modulen
    if hasattr(utils, "ensure_bytes"):
        assert utils.ensure_bytes(b"x") == b"x"
        assert utils.ensure_bytes("x") == b"x"

    if hasattr(utils, "ensure_str"):
        assert utils.ensure_str("x") == "x"
        assert utils.ensure_str(b"x") == "x"

    if hasattr(utils, "parse_bool"):
        assert utils.parse_bool(True) is True
        assert utils.parse_bool("false") is False

    if hasattr(utils, "b64e") and hasattr(utils, "b64d"):
        data = b"abc\x00"
        enc = utils.b64e(data)
        assert isinstance(enc, (str, bytes))
        dec = utils.b64d(enc)
        assert dec == data

    if hasattr(utils, "read_file_bytes"):
        p = tmp_path / "f.bin"
        p.write_bytes(b"xyz")
        assert utils.read_file_bytes(str(p)) == b"xyz"

    if hasattr(utils, "write_file_bytes"):
        p = tmp_path / "g.bin"
        utils.write_file_bytes(str(p), b"123")
        assert p.read_bytes() == b"123"
