"""Provider ABC — every LLM backend implements report synthesis + Q&A."""
from __future__ import annotations

from abc import ABC, abstractmethod

from opendna.models import AnalysisSummary, ChatTurn, Finding, SourceFileInfo

SYSTEM_PROMPT = (
    "You are OpenDNA's synthesis assistant. You receive structured findings from a consumer "
    "DNA scan (rsid, gene, genotype, rule-based interpretation, ClinVar/PharmGKB annotations). "
    "Write a concise, readable prose summary grouped by body system, flag the most important "
    "risk findings first, and note any actionable steps the user could discuss with a clinician. "
    "Never present the output as medical advice. Keep the entire response under 600 words."
)

REPORT_QA_SYSTEM_PROMPT = (
    "You are OpenDNA's report Q&A assistant. Answer the user's question using only the "
    "structured report context you are given. Prefer the explicit finding, derived insight, "
    "gene caveat, and source-file coverage details over general background. Distinguish "
    "'not tested', 'no-call', and 'normal' clearly. If the report cannot support a conclusion, "
    "say so directly. Never claim to have the raw DNA file. Never present the output as "
    "medical advice. Keep the answer concise and under 250 words unless the user asks for detail."
)


def findings_to_prompt(findings: list[Finding]) -> str:
    """Render findings as a compact structured block for the LLM."""
    lines = []
    for f in findings:
        if f.call_status != "called":
            continue
        display_genotype = f.interpreted_genotype or f.genotype or "--"
        line = f"[{f.tier}] {f.gene} {f.rsid} = {display_genotype} ({f.panel_id}) — {f.note}"
        if f.clinvar:
            line += f" | ClinVar: {f.clinvar['clinical_significance']}"
        if f.pharmgkb:
            drugs = ", ".join(r["drug"] for r in f.pharmgkb)
            line += f" | PharmGKB: {drugs}"
        lines.append(line)
    return "\n".join(lines)


def _report_findings_to_prompt(findings: list[Finding]) -> str:
    lines = []
    for f in findings:
        display_genotype = f.interpreted_genotype or f.genotype or "--"
        if f.call_status == "called":
            line = f"[{f.tier}] {f.gene} {f.rsid} = {display_genotype} ({f.panel_id}) — {f.note}"
        else:
            line = f"[{f.call_status}] {f.gene} {f.rsid} ({f.panel_id}) — {f.note}"
        if f.clinvar and f.call_status == "called":
            line += f" | ClinVar: {f.clinvar['clinical_significance']}"
        if f.pharmgkb and f.call_status == "called":
            drugs = ", ".join(r["drug"] for r in f.pharmgkb)
            line += f" | PharmGKB: {drugs}"
        lines.append(line)
    return "\n".join(lines)


def _summary_to_prompt(summary: AnalysisSummary | None) -> str:
    if summary is None:
        return ""

    sections: list[str] = []

    if summary.derived_insights:
        lines = []
        for insight in summary.derived_insights:
            genes = f" [{', '.join(insight.genes)}]" if insight.genes else ""
            lines.append(f"[{insight.tier}] {insight.title}{genes} — {insight.summary}")
        sections.append("Derived insights:\n" + "\n".join(lines))

    if summary.gene_summaries:
        lines = []
        for gene in summary.gene_summaries:
            panels = f" ({', '.join(gene.panels)})" if gene.panels else ""
            line = f"[{gene.tier}] {gene.gene}{panels} — {gene.summary}"
            if gene.caveat:
                line += f" | Caveat: {gene.caveat}"
            lines.append(line)
        sections.append("Gene summaries:\n" + "\n".join(lines))

    if summary.panel_summaries:
        lines = []
        for panel in summary.panel_summaries:
            lines.append(
                f"{panel.panel_name}: {panel.called_count}/{panel.total_snps} called, "
                f"{panel.not_tested_count} not tested, {panel.no_call_count} no-call, "
                f"{panel.ambiguous_count} ambiguous"
            )
        sections.append("Panel coverage:\n" + "\n".join(lines))

    return "\n\n".join(sections)


def _source_file_to_prompt(source_file: SourceFileInfo | None) -> str:
    if source_file is None:
        return ""

    lines = [
        f"Vendor: {source_file.vendor or 'unknown'}",
        f"Build: {source_file.build or 'unknown'}",
        f"Unique rsids: {source_file.unique_rsid_count}",
        f"No-calls: {source_file.no_call_count}",
        f"Ambiguous calls: {source_file.ambiguous_call_count}",
    ]
    if source_file.blind_spots:
        lines.append("Blind spots: " + "; ".join(source_file.blind_spots))
    if source_file.issues:
        issues = "; ".join(issue.message for issue in source_file.issues)
        lines.append("Parser issues: " + issues)
    return "Source file context:\n" + "\n".join(lines)


def report_context_to_prompt(
    findings: list[Finding],
    analysis_summary: AnalysisSummary | None = None,
    source_file: SourceFileInfo | None = None,
) -> str:
    sections = [
        "Report findings:\n" + (_report_findings_to_prompt(findings) or "(none)"),
    ]
    summary_block = _summary_to_prompt(analysis_summary)
    if summary_block:
        sections.append(summary_block)
    source_block = _source_file_to_prompt(source_file)
    if source_block:
        sections.append(source_block)
    return "\n\n".join(sections)


def report_chat_messages(
    question: str,
    findings: list[Finding],
    analysis_summary: AnalysisSummary | None = None,
    source_file: SourceFileInfo | None = None,
    history: list[ChatTurn] | None = None,
) -> list[dict[str, str]]:
    messages = [
        {
            "role": "user",
            "content": (
                "Use this filtered OpenDNA report context for the rest of this conversation. "
                "It is not the raw DNA file.\n\n"
                + report_context_to_prompt(
                    findings,
                    analysis_summary=analysis_summary,
                    source_file=source_file,
                )
            ),
        }
    ]
    for turn in (history or [])[-6:]:
        messages.append({"role": turn.role, "content": turn.content.strip()})
    messages.append({"role": "user", "content": question.strip()})
    return messages


class Provider(ABC):
    """Abstract LLM provider."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.model} api_key=***redacted***>"

    @abstractmethod
    def interpret(self, findings: list[Finding]) -> str:
        ...

    @abstractmethod
    def answer_question(
        self,
        findings: list[Finding],
        question: str,
        analysis_summary: AnalysisSummary | None = None,
        source_file: SourceFileInfo | None = None,
        history: list[ChatTurn] | None = None,
    ) -> str:
        ...
