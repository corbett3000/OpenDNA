"""Pydantic data models for OpenDNA."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["normal", "warning", "risk", "unknown"]
CallStatus = Literal["called", "not_tested", "no_call", "ambiguous"]
MatchMethod = Literal[
    "exact",
    "normalized",
    "reverse_complement",
    "unmatched",
    "not_tested",
    "no_call",
    "ambiguous",
]
ConfidenceLabel = Literal["high", "medium", "low", "none"]


class Interpretation(BaseModel):
    tier: Tier
    note: str


class SnpDef(BaseModel):
    rsid: str = Field(pattern=r"^rs\d+$")
    gene: str
    variant_name: str | None = None
    description: str
    interpretations: dict[str, Interpretation] = Field(default_factory=dict)


class Panel(BaseModel):
    id: str
    name: str
    description: str
    snps: list[SnpDef]


class Finding(BaseModel):
    panel_id: str
    rsid: str
    gene: str
    genotype: str | None
    interpreted_genotype: str | None = None
    tier: Tier
    note: str
    description: str
    call_status: CallStatus = "called"
    match_method: MatchMethod = "exact"
    confidence_score: float = 1.0
    confidence_label: ConfidenceLabel = "high"
    clinvar: dict | None = None
    pharmgkb: list[dict] | None = None


class ParseIssue(BaseModel):
    severity: Literal["info", "warning"]
    code: str
    message: str


class SourceFileInfo(BaseModel):
    path: str
    vendor: str | None = None
    build: str | None = None
    unique_rsid_count: int
    parsed_row_count: int
    malformed_row_count: int = 0
    duplicate_rsid_count: int = 0
    no_call_count: int = 0
    ambiguous_call_count: int = 0
    comment_line_count: int = 0
    chromosome_labels: list[str] = Field(default_factory=list)
    blind_spots: list[str] = Field(default_factory=list)
    issues: list[ParseIssue] = Field(default_factory=list)


class ParseResult(BaseModel):
    genotypes: dict[str, str]
    source: SourceFileInfo


class PanelSummary(BaseModel):
    panel_id: str
    panel_name: str
    total_snps: int
    called_count: int
    not_tested_count: int
    no_call_count: int
    ambiguous_count: int
    risk_count: int
    warning_count: int
    normal_count: int
    assessed_pct: int


class DerivedInsight(BaseModel):
    id: str
    title: str
    summary: str
    tier: Tier
    confidence_score: float
    confidence_label: ConfidenceLabel
    genes: list[str] = Field(default_factory=list)
    panel_ids: list[str] = Field(default_factory=list)
    rsids: list[str] = Field(default_factory=list)


class GeneSummary(BaseModel):
    gene: str
    tier: Tier
    summary: str
    panels: list[str] = Field(default_factory=list)
    rsids: list[str] = Field(default_factory=list)
    caveat: str | None = None


class AnalysisSummary(BaseModel):
    panel_summaries: list[PanelSummary] = Field(default_factory=list)
    derived_insights: list[DerivedInsight] = Field(default_factory=list)
    gene_summaries: list[GeneSummary] = Field(default_factory=list)


class ReportBundle(BaseModel):
    findings: list[Finding]
    html: str
    json_payload: dict
    llm_prose: str | None = None
    source_file: SourceFileInfo | None = None
    analysis_summary: AnalysisSummary | None = None
