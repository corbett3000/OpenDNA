"""Command-line entry point for OpenDNA."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from opendna import __version__
from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.annotations.updater import refresh
from opendna.panels import load_panels
from opendna.parser import parse_23andme
from opendna.report import render_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opendna",
        description="Local precision-medicine scans from raw DNA files.",
    )
    p.add_argument("--version", action="version", version=f"opendna {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    srv = sub.add_parser("serve", help="Start the local web UI (default port 8787).")
    srv.add_argument("--port", type=int, default=8787)
    srv.add_argument("--host", type=str, default="127.0.0.1",
                     help="Default 127.0.0.1 (localhost only). 0.0.0.0 exposes to your LAN — "
                          "only use on a trusted network.")

    scan = sub.add_parser(
        "scan",
        help="Headless scan — emits <file>.opendna.{html,json} alongside input.",
    )
    scan.add_argument("file", help="Path to 23andMe-style raw DNA TSV.")
    scan.add_argument("--panels", nargs="*", default=None,
                      help="Panel ids to include (default: all).")

    sub.add_parser("update-db", help="Report status of shipped ClinVar/PharmGKB subsets.")

    return p


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn  # deferred import to keep `scan`/`update-db` fast
    if args.host == "0.0.0.0":
        print("WARNING: Binding to 0.0.0.0 — OpenDNA is reachable from other machines on your LAN.",
              file=sys.stderr)
    uvicorn.run("opendna.server:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"error: file not found: {input_path}", file=sys.stderr)
        return 1
    parsed = parse_23andme(input_path)
    panels = load_panels()
    selected = set(args.panels) if args.panels else None
    findings = analyze(parsed, panels, selected_panel_ids=selected)
    findings = annotate(findings, load_clinvar(), load_pharmgkb())
    bundle = render_report(findings)

    html_out = input_path.with_name(input_path.stem + ".opendna.html")
    json_out = input_path.with_name(input_path.stem + ".opendna.json")
    html_out.write_text(bundle.html)
    json_out.write_text(json.dumps(bundle.json_payload, indent=2))
    print(f"Wrote {html_out}")
    print(f"Wrote {json_out}")
    return 0


def cmd_update_db(_args: argparse.Namespace) -> int:
    status = refresh()
    print(json.dumps(status, indent=2))
    return 0


DISPATCH = {"serve": cmd_serve, "scan": cmd_scan, "update-db": cmd_update_db}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return DISPATCH[args.cmd](args)
