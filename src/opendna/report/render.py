"""Jinja2-driven renderer for the OpenDNA report."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, select_autoescape

from opendna.models import AnalysisSummary, Finding, ReportBundle, SourceFileInfo
from opendna.panels import load_panels
from opendna.summaries import build_analysis_summary, gene_caveats

SCHEMA_VERSION = 1


def _group_by_panel(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.panel_id].append(f)
    return dict(sorted(grouped.items()))


def _counts_by_tier(findings: list[Finding]) -> dict[str, int]:
    counts = {"risk": 0, "warning": 0, "normal": 0, "unknown": 0}
    for f in findings:
        counts[f.tier] = counts.get(f.tier, 0) + 1
    return counts


def _panel_names() -> dict[str, str]:
    return {p.id: p.name for p in load_panels()}


def render_report(
    findings: list[Finding],
    llm_prose: str | None = None,
    source_file: SourceFileInfo | None = None,
    analysis_summary: AnalysisSummary | None = None,
) -> ReportBundle:
    template_dir = files("opendna.report")
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "html.j2"]),
    )
    template = env.get_template("template.html.j2")

    grouped = _group_by_panel(findings)
    counts = _counts_by_tier(findings)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    findings_visible = sum(1 for f in findings if f.call_status == "called")
    analysis_summary = analysis_summary or build_analysis_summary(findings, load_panels())
    critical_findings = [
        f for f in findings
        if f.tier == "risk" and f.call_status == "called"
    ][:5]

    html = template.render(
        grouped=grouped,
        counts=counts,
        llm_prose=llm_prose,
        generated_at=generated_at,
        findings_total=len(findings),
        findings_visible=findings_visible,
        critical_findings=critical_findings,
        panel_names=_panel_names(),
        source_file=source_file,
        analysis_summary=analysis_summary,
        panel_summary_map={
            summary.panel_id: summary for summary in analysis_summary.panel_summaries
        },
        gene_caveats=gene_caveats(),
    )
    json_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "findings_count": len(findings),
        "counts_by_tier": counts,
        "findings": [f.model_dump() for f in findings],
        "llm_prose": llm_prose,
        "source_file": source_file.model_dump() if source_file else None,
        "analysis_summary": analysis_summary.model_dump(),
    }
    return ReportBundle(
        findings=findings,
        html=html,
        json_payload=json_payload,
        llm_prose=llm_prose,
        source_file=source_file,
        analysis_summary=analysis_summary,
    )
