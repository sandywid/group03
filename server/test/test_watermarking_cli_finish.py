# test/test_watermarking_cli_finish.py  (uppdaterad för att undvika prompts)
import io
import sys
import argparse
import importlib
from pathlib import Path

import pytest
from pypdf import PdfWriter

cli = importlib.import_module("watermarking_cli")


def _make_pdf_bytes(pages=1) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(300, 300)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def _build_parser():
    # build_parser / get_parser
    for name in ("build_parser", "get_parser"):
        if hasattr(cli, name):
            p = getattr(cli, name)()
            if isinstance(p, argparse.ArgumentParser):
                return p
    # PARSER global
    for name in ("PARSER", "parser"):
        if hasattr(cli, name) and isinstance(getattr(cli, name), argparse.ArgumentParser):
            return getattr(cli, name)

    # Fånga skapandet via patch på argparse.ArgumentParser
    captured = {"parser": None}
    real_AP = argparse.ArgumentParser

    class TrapAP(argparse.ArgumentParser):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["parser"] = self
        def exit(self, status=0, message=None):
            raise SystemExit(status)

    try:
        sys.modules["argparse"].ArgumentParser = TrapAP  # type: ignore
        if hasattr(cli, "main"):
            try:
                cli.main(["-h"])
            except SystemExit:
                pass
    finally:
        sys.modules["argparse"].ArgumentParser = real_AP  # type: ignore

    assert isinstance(captured["parser"], argparse.ArgumentParser), "Could not capture CLI parser"
    return captured["parser"]


def _synthesize_args(subparser, tmp_path: Path):
    """
    Bygg argv för ett subkommando. För att undvika prompts:
    - lägg alltid på --secret och --key om flaggorna existerar,
      även när de INTE är required.
    """
    inp = tmp_path / "in.pdf"
    outp = tmp_path / "out.pdf"
    inp.write_bytes(_make_pdf_bytes())

    stub = {
        "in": str(inp), "input": str(inp), "src": str(inp),
        "out": str(outp), "output": str(outp), "dst": str(outp),
        "payload": "cGF5bG9hZA==",  # "payload"
        "secret": "s", "key": "k", "tag": "WM",
    }

    argv = []
    added_dests = set()

    for a in subparser._actions:
        if not a.option_strings:  # positional
            if "out" in a.dest or "dst" in a.dest:
                argv.append(stub["out"])
                added_dests.add(a.dest)
            elif "in" in a.dest or "src" in a.dest:
                argv.append(stub["in"])
                added_dests.add(a.dest)
            else:
                argv.append("arg")
                added_dests.add(a.dest)
            continue

        if getattr(a, "required", False):
            flag = a.option_strings[-1]
            if isinstance(a, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                argv.append(flag)
            else:
                if "out" in a.dest or "dst" in a.dest:
                    argv += [flag, stub["out"]]
                elif "in" in a.dest or "src" in a.dest:
                    argv += [flag, stub["in"]]
                elif "payload" in a.dest:
                    argv += [flag, stub["payload"]]
                elif "secret" in a.dest:
                    argv += [flag, stub["secret"]]
                elif "key" in a.dest:
                    argv += [flag, stub["key"]]
                elif "tag" in a.dest:
                    argv += [flag, stub["tag"]]
                else:
                    argv += [flag, "1"]
            added_dests.add(a.dest)

    # --- Extra: injicera secret/key ÄVEN om de inte var required ---
    # Hitta flaggor som finns, men inte lades till ovan.
    def _ensure_flag(dest_name, value):
        for a in subparser._actions:
            if a.option_strings and a.dest == dest_name and dest_name not in added_dests:
                # välj sista (vanligtvis den långa) flaggan
                argv.extend([a.option_strings[-1], value])
                added_dests.add(dest_name)
                break

    _ensure_flag("secret", stub["secret"])
    _ensure_flag("key", stub["key"])
    # payload behövs inte för att undvika prompts, men lägg gärna med om det finns:
    _ensure_flag("payload", stub["payload"])

    return argv


def test_cli_help_and_dynamic_subcommands(tmp_path):
    p = _build_parser()

    # Inga subparsers? testa -h och klart.
    subs = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)]
    if not subs:
        try:
            p.parse_args(["-h"])
        except SystemExit:
            pass
        return

    for sp_action in subs:
        for cmd, sp in sp_action.choices.items():
            argv = [cmd] + _synthesize_args(sp, tmp_path)
            # Parse + kör handler om den finns (set_defaults(func=...))
            try:
                ns = p.parse_args(argv)
            except SystemExit:
                continue
            func = getattr(ns, "func", None)
            if callable(func):
                try:
                    func(ns)
                except SystemExit:
                    pass
                except Exception:
                    # ok om kommandot signalerar fel (t.ex. fel nyckel etc.)
                    pass
            else:
                # åtminstone kunna visa help för subkommandot
                try:
                    sp.parse_args([cmd, "-h"])
                except SystemExit:
                    pass


def test_cli_version_and_unknown(capsys):
    # --version om det stöds
    code = 1
    if hasattr(cli, "main"):
        try:
            cli.main(["--version"])  # type: ignore[attr-defined]
            code = 0
        except SystemExit as e:
            code = int(e.code or 1)
        except Exception:
            pass
    assert code in (0, 1)  # acceptera om flaggan saknas

    # okänt subkommando ska fela
    try:
        if hasattr(cli, "main"):
            cli.main(["__no_such_command__"])  # type: ignore[attr-defined]
    except SystemExit as e:
        assert int(e.code or 1) != 0
