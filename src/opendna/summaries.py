"""Higher-level summaries layered on top of per-rsid findings."""
from __future__ import annotations

from collections import defaultdict

from opendna.models import (
    AnalysisSummary,
    DerivedInsight,
    Finding,
    GeneSummary,
    Panel,
    PanelSummary,
)

_TIER_RANK = {"risk": 3, "warning": 2, "normal": 1, "unknown": 0}

GENE_CAVEATS = {
    "AOC1": (
        "DAO genetics are only one piece of histamine tolerance. Food load, alcohol, "
        "medications, gut inflammation, and mast-cell biology can dominate symptoms."
    ),
    "APOE": (
        "APOE status here comes from rs429358 + rs7412 only; it does not capture "
        "non-APOE causes of dementia or lipid risk."
    ),
    "CYP2C19": (
        "This captures the common *2 and *17 markers only; other loss-of-function "
        "alleles are not assessed in most consumer array files."
    ),
    "CYP2C9": (
        "This covers the common *2 and *3 markers only; other CYP2C9 star alleles "
        "remain untested."
    ),
    "CYP3A5": (
        "rs776746 captures the common expressor split, not the full CYP3A5 "
        "star-allele space."
    ),
    "CYP4F2": (
        "CYP4F2 contributes modestly to warfarin dose and should be read "
        "alongside CYP2C9 and VKORC1."
    ),
    "F2": (
        "This common thrombophilia marker raises baseline clot risk but does not "
        "diagnose an active clotting disorder."
    ),
    "F5": (
        "This array marker flags inherited thrombophilia risk, not current clotting "
        "status or treatment need."
    ),
    "HFE": (
        "These common HFE variants explain many classic hemochromatosis patterns, "
        "but not every cause of iron overload or anemia."
    ),
    "HNMT": (
        "HNMT affects intracellular histamine breakdown, not the full picture of "
        "dietary histamine handling or mast-cell activation."
    ),
    "MTHFR": (
        "Common MTHFR SNPs do not directly diagnose folate deficiency; "
        "homocysteine, B12, folate, and diet still matter."
    ),
    "SLCO1B1": (
        "rs4149056 captures the best-known simvastatin myopathy signal, not the "
        "full statin-response landscape."
    ),
    "TPMT": (
        "This panel captures TPMT *3C only; other TPMT and NUDT15 variants can "
        "still be clinically important."
    ),
    "VKORC1": (
        "Warfarin response still depends on age, diet, liver function, "
        "interacting drugs, and other genes."
    ),
}


def gene_caveats() -> dict[str, str]:
    return GENE_CAVEATS.copy()


def _top_tier(*tiers: str) -> str:
    return max(tiers, key=lambda tier: _TIER_RANK[tier], default="unknown")


def _confidence_label(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= 0.6:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _canonical_genotype(finding: Finding | None) -> str | None:
    if finding is None or finding.call_status != "called":
        return None
    return finding.interpreted_genotype or finding.genotype


def _variant_count(finding: Finding | None, allele: str) -> int | None:
    genotype = _canonical_genotype(finding)
    if genotype is None:
        return None
    return genotype.count(allele)


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _unique_notes(findings: list[Finding]) -> list[str]:
    seen: list[str] = []
    for finding in findings:
        if finding.note not in seen:
            seen.append(finding.note)
    return seen


def _present_findings(*findings: Finding | None) -> list[Finding]:
    return [finding for finding in findings if finding is not None]


def _make_insight(
    insight_id: str,
    title: str,
    summary: str,
    tier: str,
    findings: list[Finding],
) -> DerivedInsight:
    confidence = min((finding.confidence_score for finding in findings), default=0.0)
    return DerivedInsight(
        id=insight_id,
        title=title,
        summary=summary,
        tier=tier,
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        genes=_unique_sorted([finding.gene for finding in findings]),
        panel_ids=_unique_sorted([finding.panel_id for finding in findings]),
        rsids=_unique_sorted([finding.rsid for finding in findings]),
    )


def _apoe_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    rs429358 = rsid_map.get("rs429358")
    rs7412 = rsid_map.get("rs7412")
    g1 = _canonical_genotype(rs429358)
    g2 = _canonical_genotype(rs7412)
    if g1 is None or g2 is None:
        return None

    mapping: dict[tuple[str, str], tuple[str, str, str]] = {
        ("TT", "TT"): (
            "normal",
            "APOE composite: e2/e2.",
            "Often associated with lower LDL, but homozygous e2 can predispose to "
            "type III hyperlipoproteinemia in the right metabolic context.",
        ),
        ("TT", "CT"): (
            "normal",
            "APOE composite: e2/e3.",
            "This usually behaves as a lower-risk APOE pattern than e3/e4 or e4/e4.",
        ),
        ("TT", "CC"): (
            "normal",
            "APOE composite: e3/e3.",
            "This is the baseline APOE pattern used for most population comparisons.",
        ),
        ("CT", "CT"): (
            "warning",
            "APOE composite: e2/e4.",
            "This is a mixed pattern: one e4 allele raises neuro/cardiometabolic "
            "risk, while one e2 allele can shift lipid behavior.",
        ),
        ("CT", "CC"): (
            "warning",
            "APOE composite: e3/e4.",
            "One e4 allele is present, which is associated with higher Alzheimer "
            "and cardiovascular risk than e3/e3.",
        ),
        ("CC", "CC"): (
            "risk",
            "APOE composite: e4/e4.",
            "Two e4 alleles are present, which is the highest-risk common APOE "
            "pattern in this assay.",
        ),
    }
    resolved = mapping.get((g1, g2))
    if resolved is None:
        return None

    tier, headline, detail = resolved
    return _make_insight(
        "apoe",
        "APOE Composite",
        f"{headline} {detail}",
        tier,
        _present_findings(rs429358, rs7412),
    )


def _hfe_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    c282y = rsid_map.get("rs1800562")
    h63d = rsid_map.get("rs1799945")
    s65c = rsid_map.get("rs1800730")
    c282y_count = _variant_count(c282y, "A")
    h63d_count = _variant_count(h63d, "G")
    s65c_count = _variant_count(s65c, "T")
    counts = [count for count in (c282y_count, h63d_count, s65c_count) if count is not None]
    if not counts:
        return None

    title = "HFE Composite"
    findings = _present_findings(c282y, h63d, s65c)
    if c282y_count == 2:
        return _make_insight(
            "hfe",
            title,
            "HFE composite: C282Y homozygous. This is the classic highest-risk "
            "common hemochromatosis pattern in consumer-array data.",
            "risk",
            findings,
        )
    if c282y_count == 1 and (h63d_count or 0) >= 1:
        return _make_insight(
            "hfe",
            title,
            "HFE composite: likely C282Y/H63D compound-carrier pattern. This "
            "meaningfully raises iron-overload risk versus either variant alone.",
            "risk",
            findings,
        )
    if c282y_count == 1 and (s65c_count or 0) >= 1:
        return _make_insight(
            "hfe",
            title,
            "HFE composite: C282Y with S65C. This is weaker than C282Y/H63D but "
            "still worth pairing with ferritin and transferrin saturation.",
            "warning",
            findings,
        )
    if (h63d_count or 0) == 2:
        return _make_insight(
            "hfe",
            title,
            "HFE composite: H63D homozygous. Penetrance is lower than C282Y, but "
            "iron studies are still worth checking if symptoms or family history fit.",
            "warning",
            findings,
        )
    if any((count or 0) >= 1 for count in (c282y_count, h63d_count, s65c_count)):
        return _make_insight(
            "hfe",
            title,
            "HFE composite: carrier signal present, but not the highest-risk "
            "common genotype combination.",
            "warning",
            findings,
        )
    return _make_insight(
        "hfe",
        title,
        "HFE composite: no common high-risk HFE pattern detected in the markers "
        "this file covers.",
        "normal",
        findings,
    )


def _cyp2c19_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    loss = rsid_map.get("rs4244285")
    gain = rsid_map.get("rs12248560")
    loss_count = _variant_count(loss, "A")
    gain_count = _variant_count(gain, "T")
    if loss_count is None or gain_count is None:
        return None

    if loss_count == 0 and gain_count == 0:
        tier = "normal"
        phenotype = "likely normal metabolizer"
    elif loss_count == 0 and gain_count == 1:
        tier = "warning"
        phenotype = "likely rapid metabolizer"
    elif loss_count == 0 and gain_count == 2:
        tier = "warning"
        phenotype = "likely ultra-rapid metabolizer"
    elif loss_count == 1 and gain_count == 0:
        tier = "warning"
        phenotype = "likely intermediate metabolizer"
    elif loss_count == 2 and gain_count == 0:
        tier = "risk"
        phenotype = "likely poor metabolizer"
    elif loss_count == 1 and gain_count == 1:
        tier = "warning"
        phenotype = "most consistent with a *2/*17 intermediate-metabolizer pattern"
    else:
        return None

    summary = (
        f"CYP2C19 composite phenotype: {phenotype}. "
        "This is more informative for clopidogrel and SSRI interpretation than "
        "reading *2 and *17 independently."
    )
    return _make_insight(
        "cyp2c19",
        "CYP2C19 Composite",
        summary,
        tier,
        _present_findings(loss, gain),
    )


def _warfarin_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    cyp2c9_2 = rsid_map.get("rs1799853")
    cyp2c9_3 = rsid_map.get("rs1057910")
    vkorc1 = rsid_map.get("rs9923231")
    cyp4f2 = rsid_map.get("rs2108622")

    reduced_2 = _variant_count(cyp2c9_2, "T")
    reduced_3 = _variant_count(cyp2c9_3, "C")
    sensitive = _variant_count(vkorc1, "T")
    offset = _variant_count(cyp4f2, "T")
    if reduced_2 is None or reduced_3 is None or sensitive is None:
        return None

    reduced_total = reduced_2 + reduced_3
    if reduced_total >= 2 and sensitive >= 1:
        tier = "risk"
        detail = (
            "Warfarin composite: strong sensitivity signal. PGx-guided dosing is "
            "strongly indicated."
        )
    elif reduced_total >= 1 and sensitive >= 1:
        tier = "risk"
        detail = (
            "Warfarin composite: both metabolism and target sensitivity markers "
            "point toward a lower starting dose."
        )
    elif reduced_total >= 2 or sensitive == 2:
        tier = "risk"
        detail = "Warfarin composite: one major sensitivity pathway is strongly shifted."
    elif reduced_total >= 1 or sensitive >= 1:
        tier = "warning"
        detail = "Warfarin composite: a moderate dose-reduction signal is present."
    elif offset and offset >= 1:
        tier = "warning"
        detail = "Warfarin composite: CYP4F2 suggests a modestly higher dose may be required."
    else:
        tier = "normal"
        detail = (
            "Warfarin composite: no common low-dose pattern was detected in the "
            "markers this file covers."
        )

    if offset and offset >= 1 and tier in {"warning", "risk"}:
        detail += (
            " CYP4F2 may modestly offset some of that sensitivity by nudging dose "
            "requirements upward."
        )

    return _make_insight(
        "warfarin",
        "Warfarin Composite",
        detail,
        tier,
        _present_findings(cyp2c9_2, cyp2c9_3, vkorc1, cyp4f2),
    )


def _mthfr_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    c677t = rsid_map.get("rs1801133")
    a1298c = rsid_map.get("rs1801131")
    c677t_count = _variant_count(c677t, "T")
    a1298c_count = _variant_count(a1298c, "C")
    if c677t_count is None or a1298c_count is None:
        return None

    if c677t_count == 2:
        tier = "risk"
        detail = (
            "MTHFR composite: C677T homozygous. This is the strongest common "
            "MTHFR signal in consumer arrays."
        )
    elif c677t_count == 1 and a1298c_count == 1:
        tier = "warning"
        detail = (
            "MTHFR composite: likely compound heterozygous C677T/A1298C pattern, "
            "which can matter more than either single heterozygous call alone."
        )
    elif c677t_count == 1 or a1298c_count >= 1:
        tier = "warning"
        detail = "MTHFR composite: one reduced-function common variant is present."
    else:
        tier = "normal"
        detail = (
            "MTHFR composite: no common reduced-function pattern detected in the "
            "markers this file covers."
        )

    return _make_insight(
        "mthfr",
        "MTHFR Composite",
        detail,
        tier,
        _present_findings(c677t, a1298c),
    )


def _histamine_insight(rsid_map: dict[str, Finding]) -> DerivedInsight | None:
    dao_16 = rsid_map.get("rs10156191")
    dao_332 = rsid_map.get("rs1049742")
    dao_664 = rsid_map.get("rs1049793")
    dao_promoter = rsid_map.get("rs2052129")
    hnmt = rsid_map.get("rs11558538")

    dao_16_count = _variant_count(dao_16, "T")
    dao_332_count = _variant_count(dao_332, "T")
    dao_664_count = _variant_count(dao_664, "G")
    dao_promoter_count = _variant_count(dao_promoter, "T")
    hnmt_count = _variant_count(hnmt, "T")

    counts = [
        count
        for count in (
            dao_16_count,
            dao_332_count,
            dao_664_count,
            dao_promoter_count,
            hnmt_count,
        )
        if count is not None
    ]
    if not counts:
        return None

    dao_total = sum(
        count or 0
        for count in (dao_16_count, dao_332_count, dao_664_count, dao_promoter_count)
    )
    hnmt_total = hnmt_count or 0

    if dao_total == 0 and hnmt_total == 0:
        tier = "normal"
        detail = (
            "Histamine composite: no reduced-clearance alleles were detected in the "
            "DAO and HNMT markers this file covered."
        )
    elif dao_total >= 4 or (dao_total >= 2 and hnmt_total >= 1) or hnmt_total == 2:
        tier = "risk"
        detail = (
            "Histamine composite: multi-hit reduced-clearance pattern across DAO/HNMT "
            "markers. This is a stronger genetic signal for lower histamine "
            "breakdown capacity."
        )
    else:
        tier = "warning"
        detail = (
            "Histamine composite: at least one reduced-clearance DAO/HNMT marker is "
            "present. This can matter more when symptoms are triggered by alcohol, "
            "high-histamine foods, gut irritation, or certain medications."
        )

    detail += (
        " This is exploratory genetics, not a diagnosis of histamine intolerance "
        "or mast-cell disease."
    )
    return _make_insight(
        "histamine",
        "Histamine Composite",
        detail,
        tier,
        _present_findings(dao_16, dao_332, dao_664, dao_promoter, hnmt),
    )


def _build_derived_insights(findings: list[Finding]) -> list[DerivedInsight]:
    rsid_map = {
        finding.rsid: finding
        for finding in findings
        if finding.call_status in {"called", "no_call", "ambiguous"}
    }
    builders = (
        _apoe_insight,
        _hfe_insight,
        _cyp2c19_insight,
        _warfarin_insight,
        _mthfr_insight,
        _histamine_insight,
    )
    insights = [insight for builder in builders if (insight := builder(rsid_map)) is not None]
    insights.sort(key=lambda item: (-_TIER_RANK[item.tier], item.title))
    return insights


def _build_panel_summaries(findings: list[Finding], panels: list[Panel]) -> list[PanelSummary]:
    findings_by_panel: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        findings_by_panel[finding.panel_id].append(finding)

    summaries: list[PanelSummary] = []
    for panel in panels:
        if panel.id not in findings_by_panel:
            continue

        items = findings_by_panel[panel.id]
        total = len(items)
        called_count = sum(item.call_status == "called" for item in items)
        not_tested_count = sum(item.call_status == "not_tested" for item in items)
        no_call_count = sum(item.call_status == "no_call" for item in items)
        ambiguous_count = sum(item.call_status == "ambiguous" for item in items)
        risk_count = sum(
            item.tier == "risk" and item.call_status == "called" for item in items
        )
        warning_count = sum(
            item.tier == "warning" and item.call_status == "called" for item in items
        )
        normal_count = sum(
            item.tier == "normal" and item.call_status == "called" for item in items
        )

        summaries.append(
            PanelSummary(
                panel_id=panel.id,
                panel_name=panel.name,
                total_snps=total,
                called_count=called_count,
                not_tested_count=not_tested_count,
                no_call_count=no_call_count,
                ambiguous_count=ambiguous_count,
                risk_count=risk_count,
                warning_count=warning_count,
                normal_count=normal_count,
                assessed_pct=int(round((called_count / total) * 100)) if total else 0,
            )
        )
    return summaries


def _build_gene_summaries(
    findings: list[Finding],
    derived_insights: list[DerivedInsight],
    panels_by_id: dict[str, str],
) -> list[GeneSummary]:
    derived_by_gene: dict[str, list[DerivedInsight]] = defaultdict(list)
    for insight in derived_insights:
        for gene in insight.genes:
            derived_by_gene[gene].append(insight)

    groups: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        if finding.call_status == "called":
            groups[finding.gene].append(finding)

    summaries: list[GeneSummary] = []
    for gene, items in groups.items():
        insights = derived_by_gene.get(gene, [])
        multi_signal = (
            len(items) > 1
            or len({item.panel_id for item in items}) > 1
            or bool(insights)
        )
        if not multi_signal:
            continue

        top_tier = _top_tier(
            *[item.tier for item in items],
            *[insight.tier for insight in insights],
        )
        summary = insights[0].summary if insights else " ".join(_unique_notes(items)[:2])
        summaries.append(
            GeneSummary(
                gene=gene,
                tier=top_tier,
                summary=summary,
                panels=_unique_sorted([panels_by_id[item.panel_id] for item in items]),
                rsids=_unique_sorted([item.rsid for item in items]),
                caveat=GENE_CAVEATS.get(gene),
            )
        )

    summaries.sort(key=lambda item: (-_TIER_RANK[item.tier], item.gene))
    return summaries


def build_analysis_summary(findings: list[Finding], panels: list[Panel]) -> AnalysisSummary:
    panels_by_id = {panel.id: panel.name for panel in panels}
    derived_insights = _build_derived_insights(findings)
    return AnalysisSummary(
        panel_summaries=_build_panel_summaries(findings, panels),
        derived_insights=derived_insights,
        gene_summaries=_build_gene_summaries(findings, derived_insights, panels_by_id),
    )
