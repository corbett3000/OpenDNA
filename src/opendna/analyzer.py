"""Analyzer — join parsed DNA with panels to produce Findings."""
from __future__ import annotations

from collections.abc import Iterable

from opendna.models import Finding, Panel, SnpDef

_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
_NO_CALL_GENOTYPES = {"--", "-", "00", "NN", "NC"}
_CONFIDENCE_SCORES = {
    "exact": 1.0,
    "normalized": 0.97,
    "reverse_complement": 0.9,
    "unmatched": 0.35,
    "not_tested": 0.0,
    "no_call": 0.0,
    "ambiguous": 0.15,
}

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


def _classify_call_status(genotype: str | None) -> str:
    if genotype is None:
        return "not_tested"
    genotype = genotype.upper()
    if genotype in _NO_CALL_GENOTYPES:
        return "no_call"
    if not genotype or len(genotype) not in {1, 2}:
        return "ambiguous"
    if any(base not in "ACGT" for base in genotype):
        return "ambiguous"
    return "called"


def _confidence_label(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= 0.6:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _match_interpretation(snp: SnpDef, genotype: str) -> tuple[str, str, str, str | None]:
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
        return i.tier, i.note, "exact", genotype
    # 2. allele-order normalization
    norm = _normalize_genotype(genotype)
    for key, interp in snp.interpretations.items():
        if _normalize_genotype(key) == norm:
            return interp.tier, interp.note, "normalized", key
    # 3. reverse-complement (only for non-palindromic sites)
    if not _is_palindromic_site(snp):
        rc = _reverse_complement(genotype)
        if rc is not None:
            rc_norm = _normalize_genotype(rc)
            for key, interp in snp.interpretations.items():
                if _normalize_genotype(key) == rc_norm:
                    return interp.tier, interp.note, "reverse_complement", key
    return "unknown", f"Genotype {genotype} not interpreted in panel.", "unmatched", None


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
            call_status = _classify_call_status(genotype)
            if call_status == "not_tested":
                findings.append(
                    Finding(
                        panel_id=panel.id,
                        rsid=snp.rsid,
                        gene=snp.gene,
                        genotype=None,
                        interpreted_genotype=None,
                        tier="unknown",
                        note="Marker not present in this source DNA file.",
                        description=snp.description,
                        call_status="not_tested",
                        match_method="not_tested",
                        confidence_score=0.0,
                        confidence_label="none",
                    )
                )
                continue
            if call_status == "no_call":
                findings.append(
                    Finding(
                        panel_id=panel.id,
                        rsid=snp.rsid,
                        gene=snp.gene,
                        genotype=genotype,
                        interpreted_genotype=None,
                        tier="unknown",
                        note=(
                            "Marker is present in the file, but the source genotype "
                            "was a no-call."
                        ),
                        description=snp.description,
                        call_status="no_call",
                        match_method="no_call",
                        confidence_score=0.0,
                        confidence_label="none",
                    )
                )
                continue
            if call_status == "ambiguous":
                findings.append(
                    Finding(
                        panel_id=panel.id,
                        rsid=snp.rsid,
                        gene=snp.gene,
                        genotype=genotype,
                        interpreted_genotype=None,
                        tier="unknown",
                        note=(
                            "Marker is present, but the source genotype format is "
                            "ambiguous for this panel."
                        ),
                        description=snp.description,
                        call_status="ambiguous",
                        match_method="ambiguous",
                        confidence_score=_CONFIDENCE_SCORES["ambiguous"],
                        confidence_label=_confidence_label(_CONFIDENCE_SCORES["ambiguous"]),
                    )
                )
                continue

            tier, note, match_method, interpreted_genotype = _match_interpretation(snp, genotype)
            confidence_score = _CONFIDENCE_SCORES[match_method]
            findings.append(
                Finding(
                    panel_id=panel.id,
                    rsid=snp.rsid,
                    gene=snp.gene,
                    genotype=genotype,
                    interpreted_genotype=interpreted_genotype,
                    tier=tier,
                    note=note,
                    description=snp.description,
                    call_status="called",
                    match_method=match_method,
                    confidence_score=confidence_score,
                    confidence_label=_confidence_label(confidence_score),
                )
            )
    return findings
