import json
from pathlib import Path

from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.models import Finding
from opendna.panels import load_panels
from opendna.parser import parse_source_file
from opendna.report import render_report
from opendna.summaries import build_analysis_summary


def _sample_findings() -> list[Finding]:
    return [
        Finding(
            panel_id="methylation",
            rsid="rs1801133",
            gene="MTHFR",
            genotype="CT",
            tier="warning",
            note="~30% reduced activity",
            description="Central methylation enzyme",
            clinvar={
                "clinical_significance": "drug response",
                "condition": "MTHFR deficiency",
                "review_status": "reviewed by expert panel",
            },
            pharmgkb=None,
        ),
        Finding(
            panel_id="pharmacogenomics",
            rsid="rs1142345",
            gene="TPMT",
            genotype="TT",
            tier="risk",
            note="Poor metabolizer",
            description="Thiopurine metabolism",
            clinvar={
                "clinical_significance": "drug response",
                "condition": "TPMT deficiency",
                "review_status": "expert panel",
            },
            pharmgkb=[
                {
                    "drug": "azathioprine",
                    "recommendation": "10-fold dose reduction",
                    "evidence_level": "1A",
                }
            ],
        ),
    ]


def test_render_report_produces_html_and_json() -> None:
    bundle = render_report(_sample_findings())
    assert "<!DOCTYPE html>" in bundle.html
    assert "MTHFR" in bundle.html
    assert "TPMT" in bundle.html
    assert bundle.json_payload["findings_count"] == 2


def test_report_html_includes_tier_badges() -> None:
    bundle = render_report(_sample_findings())
    assert "risk" in bundle.html
    assert "warning" in bundle.html


def test_report_json_is_serializable_and_round_trips() -> None:
    bundle = render_report(_sample_findings())
    roundtrip = json.loads(json.dumps(bundle.json_payload))
    assert roundtrip["findings_count"] == 2
    assert roundtrip["findings"][0]["rsid"] == "rs1801133"


def test_render_report_includes_llm_prose_when_provided() -> None:
    bundle = render_report(
        _sample_findings(),
        llm_prose="Summary: your methylation profile shows reduced MTHFR activity.",
    )
    assert "methylation profile" in bundle.html
    assert bundle.llm_prose is not None


def test_render_report_escapes_html_in_prose() -> None:
    """Jinja autoescape must neutralize LLM-supplied HTML to prevent injection."""
    bundle = render_report(_sample_findings(), llm_prose="<script>alert('xss')</script>")
    assert "<script>" not in bundle.html
    assert "&lt;script&gt;" in bundle.html


def test_render_report_includes_source_qc_and_composite_sections(fixtures_dir: Path) -> None:
    parsed = parse_source_file(fixtures_dir / "sample_23andme.txt")
    panels = load_panels()
    findings = annotate(analyze(parsed.genotypes, panels), load_clinvar(), load_pharmgkb())
    summary = build_analysis_summary(findings, panels)
    bundle = render_report(findings, source_file=parsed.source, analysis_summary=summary)
    assert "Source File Quality" in bundle.html
    assert "Composite Calls" in bundle.html
    assert "Cross-Panel Gene View" in bundle.html
    assert bundle.json_payload["source_file"]["vendor"] == "23andMe"
