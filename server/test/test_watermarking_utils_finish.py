import io
import json
import os
import importlib
import inspect
from pathlib import Path
import pytest

utils = importlib.import_module("watermarking_utils")


def _touch(tmp_path: Path, name="f.bin", data=b"xyz") -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_utils_dynamic_sweep(tmp_path, monkeypatch):
    # miljö
    monkeypatch.setenv("WM_TMP", str(tmp_path))

    sample_b = b"a\x00b\xffc"
    sample_s = "hello"
    pdf_like = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

    f_in = _touch(tmp_path, "in.pdf", pdf_like)
    f_out = tmp_path / "out.bin"
    d = tmp_path / "dir"
    d.mkdir(exist_ok=True)

    # Vanliga helpers
    if hasattr(utils, "ensure_bytes"):
        assert utils.ensure_bytes(sample_b) == sample_b
        assert utils.ensure_bytes(sample_s) == sample_s.encode()
    if hasattr(utils, "ensure_str"):
        r = utils.ensure_str(sample_b)
        assert isinstance(r, str)
        assert utils.ensure_str(sample_s) == sample_s

    if hasattr(utils, "b64e") and hasattr(utils, "b64d"):
        enc = utils.b64e(sample_b)
        if isinstance(enc, bytes):
            enc = enc.decode("ascii", "ignore")
        assert utils.b64d(enc) == sample_b

    if hasattr(utils, "parse_bool"):
        for v in (True, False, "true", "False", "0", "nonsense"):
            utils.parse_bool(v)

    if hasattr(utils, "safe_int"):
        assert utils.safe_int("12", default=-1) == 12
        assert utils.safe_int("xx", default=-1) == -1

    if hasattr(utils, "json_dumps") and hasattr(utils, "json_loads"):
        s = utils.json_dumps({"a": 1, "b": "c"})
        assert utils.json_loads(s) == {"a": 1, "b": "c"}

    if hasattr(utils, "expand_path"):
        utils.expand_path(str(f_in))
        utils.expand_path(str(Path("~").expanduser()))
        utils.expand_path("$WM_TMP/file.txt")

    if hasattr(utils, "ensure_dir"):
        utils.ensure_dir(str(d / "nested"))

    if hasattr(utils, "temp_filename"):
        t = utils.temp_filename(prefix="wm_", suffix=".tmp", dir=str(tmp_path))
        Path(t).write_bytes(b"x")
        assert Path(t).exists()

    if hasattr(utils, "write_file_bytes"):
        utils.write_file_bytes(str(f_out), b"123")
    if hasattr(utils, "read_file_bytes"):
        assert utils.read_file_bytes(str(f_in)).startswith(b"%PDF")

    if hasattr(utils, "slugify"):
        utils.slugify("A b/C:D.é")
    if hasattr(utils, "guess_mime"):
        utils.guess_mime(str(f_in))
        utils.guess_mime("weird.ext")

    if hasattr(utils, "chunk_bytes"):
        assert list(utils.chunk_bytes(b"abcdef", 2)) == [b"ab", b"cd", b"ef"]
    if hasattr(utils, "xor_bytes"):
        utils.xor_bytes(b"\x0f\x00", b"\xf0\xf0")

    for name in ["hexdump", "shorten", "trim_nonprintable",
                 "looks_like_pdf", "is_pdf_bytes", "is_probably_pdf"]:
        if hasattr(utils, name):
            getattr(utils, name)(sample_b)

    # Svep igenom kvarvarande publika callables “best effort”
    for name in dir(utils):
        if name.startswith("_"):
            continue
        obj = getattr(utils, name)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
            except Exception:
                continue
            args = []
            for p in sig.parameters.values():
                if p.default is not p.empty:
                    continue
                n = p.name.lower()
                if any(k in n for k in ("path", "file", "name")):
                    args.append(str(f_in))
                elif any(k in n for k in ("data", "bytes", "payload", "buf")):
                    args.append(sample_b)
                elif any(k in n for k in ("text", "str")):
                    args.append(sample_s)
                elif any(k in n for k in ("size", "len", "chunk")):
                    args.append(2)
                else:
                    args.append(sample_s)
            try:
                obj(*args)
            except Exception:
                pass
