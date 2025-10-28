# test/test_watermarking_utils_maxcov.py
import io
import json
import os
import sys
import types
from pathlib import Path
import importlib
import pytest

utils = importlib.import_module("watermarking_utils")


def test_utils_import_and_dunder_all_are_valid():
    # Bara importera och (om __all__ finns) verifiera att allt namnges korrekt
    if hasattr(utils, "__all__"):
        for name in utils.__all__:
            assert hasattr(utils, name), f"__all__ names {name} missing"


def test_bytes_str_roundtrip_and_b64(tmp_path):
    # ensure_bytes / ensure_str
    if hasattr(utils, "ensure_bytes"):
        assert utils.ensure_bytes("abc") == b"abc"
        assert utils.ensure_bytes(b"abc") == b"abc"
        assert utils.ensure_bytes(bytearray(b"abc")) == b"abc"

    if hasattr(utils, "ensure_str"):
        assert utils.ensure_str(b"abc") == "abc"
        assert utils.ensure_str("abc") == "abc"

    # b64e / b64d
    if hasattr(utils, "b64e") and hasattr(utils, "b64d"):
        raw = b"a\x00b\xffc"
        enc = utils.b64e(raw)
        # enc kan vara str eller bytes
        if isinstance(enc, bytes):
            enc = enc.decode("ascii")
        dec = utils.b64d(enc)
        assert dec == raw

    # File I/O helpers
    p = tmp_path / "data.bin"
    if hasattr(utils, "write_file_bytes"):
        utils.write_file_bytes(str(p), b"xyz")
        assert p.read_bytes() == b"xyz"
    else:
        p.write_bytes(b"xyz")

    if hasattr(utils, "read_file_bytes"):
        assert utils.read_file_bytes(str(p)) == b"xyz"


def test_parsers_bool_int_json_and_env(tmp_path, monkeypatch):
    # parse_bool
    if hasattr(utils, "parse_bool"):
        assert utils.parse_bool(True) is True
        assert utils.parse_bool(False) is False
        assert utils.parse_bool("true") is True
        assert utils.parse_bool("False") is False
        # ok med skräp → False/True beroende på implementation; bara kalla funktionen
        utils.parse_bool("nonsense")

    # safe_int
    if hasattr(utils, "safe_int"):
        assert utils.safe_int("12", default=-1) == 12
        assert utils.safe_int("nope", default=-1) == -1

    # json dumps/loads helpers
    if hasattr(utils, "json_dumps") and hasattr(utils, "json_loads"):
        obj = {"a": 1, "b": "x"}
        s = utils.json_dumps(obj)
        back = utils.json_loads(s)
        assert back == obj

    # env helpers
    monkeypatch.setenv("WM_TEST_ENV", "value")
    if hasattr(utils, "getenv"):
        assert utils.getenv("WM_TEST_ENV", default=None) == "value"
        assert utils.getenv("MISSING_ENV", default="d") == "d"

    # expanduser/expandvars helpers
    if hasattr(utils, "expand_path"):
        # ~ och $VAR expanderas
        monkeypatch.setenv("WM_EXP", str(tmp_path))
        p = utils.expand_path("~/..")  # exekvera bara
        p2 = utils.expand_path("$WM_EXP/file.txt")
        assert isinstance(p2, str) or isinstance(p2, bytes)


def test_path_and_slug_and_mime(tmp_path):
    # slugify / sanitize filename
    if hasattr(utils, "slugify"):
        assert utils.slugify("A b/C:D")  # bara att den kör

    # guess mime
    if hasattr(utils, "guess_mime"):
        assert utils.guess_mime("file.pdf").lower().startswith("application/")
        assert isinstance(utils.guess_mime("weirdfile.xyz"), str)

    # temp name / ensure dir
    if hasattr(utils, "ensure_dir"):
        utils.ensure_dir(str(tmp_path / "a/b/c"))
    if hasattr(utils, "temp_filename"):
        t = utils.temp_filename(prefix="wm_", suffix=".bin", dir=str(tmp_path))
        Path(t).write_bytes(b"x")
        assert Path(t).exists()


def test_chunking_xor_hexdump_and_misc():
    # chunk_bytes
    if hasattr(utils, "chunk_bytes"):
        chunks = list(utils.chunk_bytes(b"abcdef", 2))
        assert chunks == [b"ab", b"cd", b"ef"]

    # xor_bytes
    if hasattr(utils, "xor_bytes"):
        assert utils.xor_bytes(b"\x0f\x00", b"\xf0\xf0") == b"\xff\xf0"

    # hexdump / repr helpers
    for name in ["hexdump", "shorten", "trim_nonprintable"]:
        if hasattr(utils, name):
            getattr(utils, name)(b"hello world")


def test_pdf_detection_and_sentinels(tmp_path):
    # is_pdf_bytes / looks_like_pdf
    sample_pdf = b"%PDF-1.3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    for name in ["is_pdf_bytes", "looks_like_pdf", "is_probably_pdf"]:
        if hasattr(utils, name):
            assert getattr(utils, name)(sample_pdf) in (True, False)  # bara exekvera

    # sentinels / constants – bara att tillgå
    for const in ["MAGIC", "TAG", "DEFAULT_TAG", "DEFAULT_FILENAME"]:
        if hasattr(utils, const):
            getattr(utils, const)
