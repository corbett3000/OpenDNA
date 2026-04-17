"""Analyzer — join parsed DNA with panels to produce Findings."""
from __future__ import annotations

from collections.abc import Iterable

from opendna.models import Finding, Panel, SnpDef

_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}

# A/T and C/G are palindromic sites: forward and reverse complements collide,
# so RC inference is unreliable. Panels whose allele set is exactly one of
# these pairs are skipped in the RC fallback.
_PALINDROMIC_PAIRS = ({"A", "T"}, {"C", "G"})


def _normalize_genotype(g: str) -> str:
    """Sort allele letters so AG == GA, AT == TA, etc.

    Single-allele (hemizygous) or indel calls are returned unchanged.
    """
    if len(g) == 2 and g.isalpha():
        return "".join(sorted(g.upper()))
    return g.upper()


def _reverse_complement(g: str) -> str | None:
    """Return the reverse-complement genotype, or None for non-ACGT calls."""
    if not g or not g.isalpha():
        return None
    rc_chars = []
    for c in g.upper():
        comp = _COMPLEMENT.get(c)
        if comp is None:
            return None
        rc_chars.append(comp)
    return "".join(rc_chars)


def _panel_alleles(snp: SnpDef) -> set[str]:
    """Alleles appearing in the panel's interpretation keys (A/C/G/T)."""
    alleles: set[str] = set()
    for key in snp.interpretations:
        for c in key.upper():
            if c in "ACGT":
                alleles.add(c)
    return alleles


def _is_palindromic_site(snp: SnpDef) -> bool:
    return _panel_alleles(snp) in _PALINDROMIC_PAIRS


def _match_interpretation(snp: SnpDef, genotype: str) -> tuple[str, str]:
    """Match a genotype to a panel interpretation.

    Fallback chain:
    1. Exact key match (e.g. "CC" == "CC").
    2. Allele-order normalization ("AG" matches "GA").
    3. Reverse-complement — for non-palindromic sites where the user's
       file reports the opposite strand (e.g. panel "CC" matches user "GG"
       for a C/T SNP reported on the reverse strand).
    """
    # 1. exact
    if genotype in snp.interpretations:
        i = snp.interpretations[genotype]
        return i.tier, i.note
    # 2. allele-order normalization
    norm = _normalize_genotype(genotype)
    for key, interp in snp.interpretations.items():
        if _normalize_genotype(key) == norm:
            return interp.tier, interp.note
    # 3. reverse-complement (only for non-palindromic sites)
    if not _is_palindromic_site(snp):
        rc = _reverse_complement(genotype)
        if rc is not None:
            rc_norm = _normalize_genotype(rc)
            for key, interp in snp.interpretations.items():
                if _normalize_genotype(key) == rc_norm:
                    return interp.tier, interp.note
    return "unknown", f"Genotype {genotype} not interpreted in panel."


def analyze(
    parsed: dict[str, str],
    panels: Iterable[Panel],
    selected_panel_ids: set[str] | None = None,
) -> list[Finding]:
    """Run every SNP in each selected panel against the parsed genotypes."""
    findings: list[Finding] = []
    for panel in panels:
        if selected_panel_ids is not None and panel.id not in selected_panel_ids:
            continue
        for snp in panel.snps:
            genotype = parsed.get(snp.rsid)
            if genotype is None:
                findings.append(
                    Finding(
                        panel_id=panel.id,
                        rsid=snp.rsid,
                        gene=snp.gene,
                        genotype=None,
                        tier="unknown",
                        note="SNP not present in raw DNA file.",
                        description=snp.description,
                    )
                )
                continue
            tier, note = _match_interpretation(snp, genotype)
            findings.append(
                Finding(
                    panel_id=panel.id,
                    rsid=snp.rsid,
                    gene=snp.gene,
                    genotype=genotype,
                    tier=tier,
                    note=note,
                    description=snp.description,
                )
            )
    return findings
