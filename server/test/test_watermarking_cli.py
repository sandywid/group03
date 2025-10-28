# test/test_watermarking_cli.py
import io
import sys
import importlib
from pathlib import Path

import pytest

cli = importlib.import_module("watermarking_cli")


def _call_main(argv, capsys):
    """
    Kör cli.main(argv) om det finns; annars importerar modulen vilket låter argparse
    köra via top-level och kasta SystemExit. Returnerar (code, out, err).
    """
    if hasattr(cli, "main"):
        try:
            cli.main(argv)  # type: ignore[attr-defined]
            out, err = capsys.readouterr()
            return 0, out, err
        except SystemExit as e:
            out, err = capsys.readouterr()
            return int(e.code or 0), out, err
    else:
        # Falla tillbaka: simulera __main__-körning med sys.argv
        old = sys.argv[:]
        sys.argv = ["watermarking_cli"] + argv
        try:
            importlib.reload(cli)
        except SystemExit as e:
            out = ""  # inget capsys här, men pytest fångar
            err = ""
            return int(e.code or 0), out, err
        finally:
            sys.argv = old
        return 0, "", ""


def test_cli_help_shows_usage(capsys):
    code, out, err = _call_main(["-h"], capsys)
    # argparse help ska avsluta med 0
    assert code == 0
    text = out or err
    assert "usage" in text.lower() or "--help" in text.lower()


def test_cli_rejects_unknown_method(capsys, tmp_path):
    # De flesta CLI har en 'method' / subcommand; prova något nonsens och förvänta SystemExit != 0
    code, out, err = _call_main(["unknown-method"], capsys)
    assert code != 0
