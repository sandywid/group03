# test/test_watermarking_cli_finishhim.py
import io
import sys
import argparse
import importlib
import runpy
from pathlib import Path

import pytest
from pypdf import PdfWriter


def _pdf_bytes(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def _ns(**kw):
    return argparse.Namespace(**kw)


def test_cli_helpers_file_and_stdin_branches(tmp_path, monkeypatch):
    """Träffar 51–52, 56–59, 64/66/68/70, 75/77/79/81–83."""
    cli = importlib.import_module("watermarking_cli")

    # 51–52: _read_text_from_file
    p = tmp_path / "s.txt"
    p.write_text("hello\nworld", encoding="utf-8")
    assert cli._read_text_from_file(str(p)) == "hello\nworld"

    # 56–59: _read_text_from_stdin med tom stdin → ValueError
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b""), encoding="utf-8"))
    with pytest.raises(ValueError):
        cli._read_text_from_stdin()

    # 64: secret direkt i args
    assert cli._resolve_secret(_ns(secret="S", secret_file=None, secret_stdin=False)) == "S"

    # 66: secret_file
    assert cli._resolve_secret(_ns(secret=None, secret_file=str(p), secret_stdin=False)) == "hello\nworld"

    # 68: secret_stdin
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"stdin-secret"), encoding="utf-8"))
    assert cli._resolve_secret(_ns(secret=None, secret_file=None, secret_stdin=True)) == "stdin-secret"

    # 70 (fallback/prompt): mocka getpass
    monkeypatch.setattr(cli, "getpass", type("G", (), {"getpass": staticmethod(lambda prompt="": "P")}))
    assert cli._resolve_secret(_ns(secret=None, secret_file=None, secret_stdin=False)) == "P"

    # 75: key direkt
    assert cli._resolve_key(_ns(key="K", key_file=None, key_stdin=False, key_prompt=False)) == "K"

    # 77: key_file
    p2 = tmp_path / "k.txt"
    p2.write_text("file-key\n", encoding="utf-8")
    assert cli._resolve_key(_ns(key=None, key_file=str(p2), key_stdin=False, key_prompt=False)) == "file-key"

    # 79: key_stdin
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"stdin-key\r\n"), encoding="utf-8"))
    assert cli._resolve_key(_ns(key=None, key_file=None, key_stdin=True, key_prompt=False)) == "stdin-key"

    # 81–83: key_prompt / fallback prompt
    assert cli._resolve_key(_ns(key=None, key_file=None, key_stdin=False, key_prompt=True)) == "P"
    # utan flaggor → fallback prompt igen
    assert cli._resolve_key(_ns(key=None, key_file=None, key_stdin=False, key_prompt=False)) == "P"


def test_cmd_explore_writes_out_file(tmp_path):
    """Träffar 96–104 och specifikt 99–100 (skriv till fil)."""
    cli = importlib.import_module("watermarking_cli")
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes())
    out_json = tmp_path / "tree.json"
    args = _ns(input=str(inp), out=str(out_json))
    rc = cli.cmd_explore(args)
    assert rc == 0 and out_json.exists() and out_json.stat().st_size > 0


def test_cmd_embed_not_applicable_hits_111_112(monkeypatch, tmp_path):
    """Tvinga is_watermarking_applicable=False → gren 111–112."""
    cli = importlib.import_module("watermarking_cli")
    inp = tmp_path / "in.pdf"
    inp.write_bytes(_pdf_bytes())
    outp = tmp_path / "out.pdf"

    monkeypatch.setattr(cli, "is_watermarking_applicable", lambda **kw: False)

    args = _ns(
        input=str(inp),
        output=str(outp),
        method="toy-eof",
        position=None,
        # så att resolvers inte försöker läsa I/O:
        key="k", key_file=None, key_stdin=False, key_prompt=False,
        secret="s", secret_file=None, secret_stdin=False,
    )
    rc = cli.cmd_embed(args)
    assert rc == 5


@pytest.mark.parametrize(
    "exc,code",
    [
        (FileNotFoundError("x"), 2),
        (ValueError("x"), 2),
        (importlib.import_module("watermarking_method").SecretNotFoundError("x"), 3),
        (importlib.import_module("watermarking_method").InvalidKeyError("x"), 4),
        (importlib.import_module("watermarking_method").WatermarkingError("x"), 5),
    ],
)
def test_main_try_except_mapping(monkeypatch, exc, code):
    """
    Träffar 223–239 genom att låta args.func kasta olika undantag.
    """
    cli = importlib.import_module("watermarking_cli")

    # bygg en minimal parser via build_parser, men monkeypatcha subkommandot "methods"
    def boom(_args):
        raise exc

    monkeypatch.setattr(cli, "cmd_methods", boom)
    rc = cli.main(["methods"])
    assert rc == code


def test_cli_main_block_runs(monkeypatch):
    """Träffar 242–243 genom att köra som __main__."""
    monkeypatch.setenv("PYTHONPATH", ":".join(sys.path))
    argv_old = sys.argv[:]
    try:
        sys.argv = ["watermarking_cli", "methods"]
        # cmd_methods är redan patchad i andra testet ibland; säkerställ no-op:
        mod = importlib.import_module("watermarking_cli")
        monkeypatch.setattr(mod, "cmd_methods", lambda _a: 0, raising=True)
        try:
            runpy.run_module("watermarking_cli", run_name="__main__")
        except SystemExit:
            pass
    finally:
        sys.argv = argv_old
