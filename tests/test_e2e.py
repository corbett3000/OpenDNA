"""End-to-end: fixture DNA file → analyze endpoint → assert report shape."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from opendna.server import app


def test_full_pipeline_rule_based(fixtures_dir: Path) -> None:
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": str(fixtures_dir / "sample_23andme.txt"),
        "selected_panels": None,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_html"].startswith("<!DOCTYPE html>")
    payload = body["report_json"]

    rsids = {f["rsid"] for f in payload["findings"] if f["genotype"]}
    assert "rs1801133" in rsids
    assert "rs4680" in rsids
    assert "rs1815739" in rsids
    assert "rs1142345" in rsids

    tpmt = next(f for f in payload["findings"] if f["rsid"] == "rs1142345")
    assert tpmt["tier"] == "risk"
    assert tpmt["pharmgkb"] is not None


def test_full_pipeline_with_mocked_llm(fixtures_dir: Path) -> None:
    client = TestClient(app)
    with patch("opendna.server.get_provider") as mock_get:
        mock_get.return_value.interpret.return_value = "End-to-end prose from mock."
        resp = client.post("/api/analyze", json={
            "file_path": str(fixtures_dir / "sample_23andme.txt"),
            "selected_panels": None,
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-fake"},
        })
    assert resp.status_code == 200
    assert "End-to-end prose from mock." in resp.json()["report_html"]
