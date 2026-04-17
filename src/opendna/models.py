"""Pydantic data models for OpenDNA."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["normal", "warning", "risk", "unknown"]


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
    tier: Tier
    note: str
    description: str
    clinvar: dict | None = None
    pharmgkb: list[dict] | None = None


class ReportBundle(BaseModel):
    findings: list[Finding]
    html: str
    json_payload: dict
    llm_prose: str | None = None
