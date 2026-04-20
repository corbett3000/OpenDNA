from pathlib import Path

from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.panels import load_panels
from opendna.parser import parse_source_file
from opendna.summaries import build_analysis_summary


def test_build_analysis_summary_from_fixture(fixtures_dir: Path) -> None:
    parsed = parse_source_file(fixtures_dir / "sample_23andme.txt")
    panels = load_panels()
    findings = annotate(analyze(parsed.genotypes, panels), load_clinvar(), load_pharmgkb())
    summary = build_analysis_summary(findings, panels)

    ids = {item.id for item in summary.derived_insights}
    assert "apoe" in ids
    assert "mthfr" in ids

    methylation = next(item for item in summary.panel_summaries if item.panel_id == "methylation")
    assert methylation.called_count == 3
    assert methylation.not_tested_count == 5

    comt = next(item for item in summary.gene_summaries if item.gene == "COMT")
    assert "Stimulant & Adenosine Sensitivity" in comt.panels
    assert "Methylation & Detox" in comt.panels


def test_build_analysis_summary_infers_histamine_composite() -> None:
    panels = load_panels()
    findings = annotate(
        analyze(
            {
                "rs10156191": "TT",
                "rs1049742": "CT",
                "rs1049793": "CG",
                "rs2052129": "GT",
                "rs11558538": "CT",
            },
            panels,
            selected_panel_ids={"histamine"},
        ),
        load_clinvar(),
        load_pharmgkb(),
    )
    summary = build_analysis_summary(findings, panels)
    histamine = next(item for item in summary.derived_insights if item.id == "histamine")
    aoc1 = next(item for item in summary.gene_summaries if item.gene == "AOC1")
    assert histamine.tier == "risk"
    assert "histamine composite" in histamine.summary.lower()
    assert "exploratory genetics" in histamine.summary.lower()
    assert aoc1.caveat is not None


def test_build_analysis_summary_infers_cyp2c19_and_warfarin_composites() -> None:
    panels = load_panels()
    findings = annotate(
        analyze(
            {
                "rs4244285": "AG",
                "rs12248560": "CT",
                "rs1799853": "CT",
                "rs1057910": "AA",
                "rs9923231": "TT",
                "rs2108622": "CT",
                "rs4149056": "CT",
                "rs2231142": "AC",
                "rs3918290": "AG",
                "rs56038477": "AG",
            },
            panels,
            selected_panel_ids={"pharmacogenomics"},
        ),
        load_clinvar(),
        load_pharmgkb(),
    )
    summary = build_analysis_summary(findings, panels)
    cyp2c19 = next(item for item in summary.derived_insights if item.id == "cyp2c19")
    dpyd = next(item for item in summary.derived_insights if item.id == "dpyd")
    statin = next(item for item in summary.derived_insights if item.id == "statin")
    warfarin = next(item for item in summary.derived_insights if item.id == "warfarin")
    assert cyp2c19.tier == "warning"
    assert "intermediate" in cyp2c19.summary
    assert dpyd.tier == "risk"
    assert "fluoropyrimidine" in dpyd.summary.lower()
    assert statin.tier == "risk"
    assert "statin composite" in statin.title.lower()
    assert warfarin.tier == "risk"
    assert "warfarin" in warfarin.summary.lower()


def test_build_analysis_summary_infers_amd_vitamin_d_and_nicotine_composites() -> None:
    panels = load_panels()
    findings = annotate(
        analyze(
            {
                "rs1061170": "CC",
                "rs10490924": "GT",
                "rs2230199": "CG",
                "rs12785878": "GG",
                "rs10741657": "AG",
                "rs2282679": "GG",
                "rs2228570": "AA",
                "rs16969968": "AG",
                "rs1051730": "AG",
                "rs588765": "CT",
            },
            panels,
            selected_panel_ids={"eye_health", "vitamin_d", "nicotine"},
        ),
        load_clinvar(),
        load_pharmgkb(),
    )
    summary = build_analysis_summary(findings, panels)
    amd = next(item for item in summary.derived_insights if item.id == "amd")
    vitamin_d = next(item for item in summary.derived_insights if item.id == "vitamin_d")
    nicotine = next(item for item in summary.derived_insights if item.id == "nicotine")
    chrna5 = next(item for item in summary.gene_summaries if item.gene == "CHRNA5")
    gc = next(item for item in summary.gene_summaries if item.gene == "GC")
    assert amd.tier == "risk"
    assert "predisposition" in amd.summary.lower() or "susceptibility" in amd.summary.lower()
    assert vitamin_d.tier == "risk"
    assert "lab" in vitamin_d.summary.lower()
    assert nicotine.tier == "risk"
    assert (
        "behavioral predisposition" in nicotine.summary.lower()
        or "dependence-prone" in nicotine.summary.lower()
    )
    assert chrna5.caveat is not None
    assert gc.caveat is not None


def test_build_analysis_summary_infers_alcohol_and_caffeine_composites() -> None:
    panels = load_panels()
    findings = annotate(
        analyze(
            {
                "rs671": "AG",
                "rs1229984": "AG",
                "rs762551": "AC",
                "rs5751876": "CT",
                "rs2472297": "CT",
            },
            panels,
            selected_panel_ids={"dietary", "sensitivity"},
        ),
        load_clinvar(),
        load_pharmgkb(),
    )
    summary = build_analysis_summary(findings, panels)
    alcohol = next(item for item in summary.derived_insights if item.id == "alcohol")
    caffeine = next(item for item in summary.derived_insights if item.id == "caffeine")
    aldh2 = next(item for item in summary.gene_summaries if item.gene == "ALDH2")
    adh1b = next(item for item in summary.gene_summaries if item.gene == "ADH1B")
    assert alcohol.tier == "risk"
    assert "acetaldehyde" in alcohol.summary.lower()
    assert caffeine.tier == "risk"
    assert "slower cyp1a2 clearance" in caffeine.summary.lower()
    assert aldh2.caveat is None
    assert adh1b.caveat is not None
