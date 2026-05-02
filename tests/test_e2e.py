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
    assert payload["source_file"]["vendor"] == "23andMe"
    assert "analysis_summary" in payload

    rsids = {f["rsid"] for f in payload["findings"] if f["genotype"]}
    assert "rs1801133" in rsids
    assert "rs4680" in rsids
    assert "rs1815739" in rsids
    assert "rs1142345" in rsids

    tpmt = next(f for f in payload["findings"] if f["rsid"] == "rs1142345")
    assert tpmt["tier"] == "risk"
    assert tpmt["pharmgkb"] is not None

    derived_ids = {item["id"] for item in payload["analysis_summary"]["derived_insights"]}
    assert "mthfr" in derived_ids
    assert "apoe" in derived_ids


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


def test_report_chat_endpoint_with_mocked_llm() -> None:
    client = TestClient(app)
    with patch("opendna.server.get_provider") as mock_get:
        mock_get.return_value.answer_question.return_value = (
            "COMT rs4680 is present in this report."
        )
        resp = client.post("/api/report-chat", json={
            "question": "Anything about COMT?",
            "findings": [
                {
                    "panel_id": "methylation",
                    "rsid": "rs4680",
                    "gene": "COMT",
                    "genotype": "AG",
                    "tier": "warning",
                    "note": "Intermediate COMT activity",
                    "description": "Catechol-O-methyltransferase",
                }
            ],
            "analysis_summary": None,
            "source_file": None,
            "history": [{"role": "user", "content": "Start with the basics."}],
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-fake"},
        })

    assert resp.status_code == 200
    assert resp.json()["answer"] == "COMT rs4680 is present in this report."
    call_kwargs = mock_get.return_value.answer_question.call_args.kwargs
    assert call_kwargs["question"] == "Anything about COMT?"
    assert call_kwargs["history"][0].content == "Start with the basics."
