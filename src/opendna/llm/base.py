"""Provider ABC — every LLM backend implements `interpret`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from opendna.models import Finding

SYSTEM_PROMPT = (
    "You are OpenDNA's synthesis assistant. You receive structured findings from a consumer "
    "DNA scan (rsid, gene, genotype, rule-based interpretation, ClinVar/PharmGKB annotations). "
    "Write a concise, readable prose summary grouped by body system, flag the most important "
    "risk findings first, and note any actionable steps the user could discuss with a clinician. "
    "Never present the output as medical advice. Keep the entire response under 600 words."
)


def findings_to_prompt(findings: list[Finding]) -> str:
    """Render findings as a compact structured block for the LLM."""
    lines = []
    for f in findings:
        line = f"[{f.tier}] {f.gene} {f.rsid} = {f.genotype or '--'} ({f.panel_id}) — {f.note}"
        if f.clinvar:
            line += f" | ClinVar: {f.clinvar['clinical_significance']}"
        if f.pharmgkb:
            drugs = ", ".join(r["drug"] for r in f.pharmgkb)
            line += f" | PharmGKB: {drugs}"
        lines.append(line)
    return "\n".join(lines)


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
