from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from opendna.server import app


def test_get_root_serves_spa() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OpenDNA" in resp.text


def test_list_panels_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/api/panels")
    assert resp.status_code == 200
    body = resp.json()
    assert "panels" in body
    ids = {p["id"] for p in body["panels"]}
    assert "methylation" in ids


def test_analyze_endpoint_returns_findings_without_llm(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text(
        "# header\n"
        "rs1801133\t1\t1000\tCT\n"
        "rs4680\t22\t2000\tGG\n"
    )
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": str(dna),
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_html"].startswith("<!DOCTYPE html>")
    assert "findings" in body["report_json"]
    assert body["report_json"]["findings_count"] >= 2


def test_analyze_endpoint_rejects_missing_file() -> None:
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": "/tmp/definitely-does-not-exist.txt",
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


def test_analyze_endpoint_invokes_llm_when_configured(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text("rs1801133\t1\t1000\tCT\n")
    client = TestClient(app)

    with patch("opendna.server.get_provider") as mock_get:
        mock_get.return_value.interpret.return_value = "AI synthesis goes here."
        resp = client.post("/api/analyze", json={
            "file_path": str(dna),
            "selected_panels": ["methylation"],
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-fake"},
        })

    assert resp.status_code == 200
    assert "AI synthesis goes here." in resp.json()["report_html"]
    mock_get.assert_called_once_with("anthropic", api_key="sk-fake", model="claude-sonnet-4-6")


def test_update_db_endpoint_returns_status() -> None:
    client = TestClient(app)
    resp = client.post("/api/update-db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "shipped-subset"


def test_analyze_stream_emits_progress_then_complete(tmp_path: Path) -> None:
    import json as json_lib

    dna = tmp_path / "dna.txt"
    dna.write_text("rs1801133\t1\t1000\tCT\nrs4680\t22\t2000\tGG\n")
    client = TestClient(app)
    resp = client.post("/api/analyze-stream", json={
        "file_path": str(dna),
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = []
    for chunk in resp.text.split("\n\n"):
        if not chunk.strip():
            continue
        ev = {"type": None, "data": None}
        for line in chunk.splitlines():
            if line.startswith("event: "):
                ev["type"] = line[7:].strip()
            elif line.startswith("data: "):
                ev["data"] = json_lib.loads(line[6:])
        events.append(ev)

    progress_events = [e for e in events if e["type"] == "progress"]
    complete_events = [e for e in events if e["type"] == "complete"]
    assert len(progress_events) >= 3, "expected multiple progress events"
    assert len(complete_events) == 1
    final = complete_events[0]["data"]
    assert final["pct"] == 100
    assert final["report_html"].startswith("<!DOCTYPE html>")
    assert final["report_json"]["findings_count"] >= 2


def test_analyze_stream_emits_error_on_missing_file() -> None:
    import json as json_lib

    client = TestClient(app)
    resp = client.post("/api/analyze-stream", json={
        "file_path": "/tmp/definitely-does-not-exist.txt",
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 200  # errors are in-band SSE events
    errors = [
        json_lib.loads(line[6:])
        for chunk in resp.text.split("\n\n")
        for line in chunk.splitlines()
        if line.startswith("data: ") and "error" in chunk.split("\n", 1)[0]
    ]
    assert any("not found" in e.get("detail", "").lower() for e in errors)
