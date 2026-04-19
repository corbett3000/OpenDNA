import json
from pathlib import Path

from opendna.cli import build_parser, cmd_scan, cmd_update_db


def test_parser_accepts_three_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "--port", "9000"])
    assert args.cmd == "serve" and args.port == 9000
    args = parser.parse_args(["scan", "foo.txt"])
    assert args.cmd == "scan" and args.file == "foo.txt"
    args = parser.parse_args(["update-db"])
    assert args.cmd == "update-db"


def test_cmd_scan_writes_html_and_json_alongside_input(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text("rs1801133\t1\t1000\tCT\nrs4680\t22\t2000\tGG\n")
    parser = build_parser()
    args = parser.parse_args(["scan", str(dna)])
    rc = cmd_scan(args)
    assert rc == 0
    html = tmp_path / "dna.opendna.html"
    js = tmp_path / "dna.opendna.json"
    assert html.exists() and js.exists()
    payload = json.loads(js.read_text())
    assert payload["findings_count"] >= 2
    assert payload["source_file"]["unique_rsid_count"] == 2
    assert "analysis_summary" in payload


def test_cmd_update_db_prints_status(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["update-db"])
    rc = cmd_update_db(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "shipped-subset" in out
