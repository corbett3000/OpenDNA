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
            },
            panels,
            selected_panel_ids={"pharmacogenomics"},
        ),
        load_clinvar(),
        load_pharmgkb(),
    )
    summary = build_analysis_summary(findings, panels)
    cyp2c19 = next(item for item in summary.derived_insights if item.id == "cyp2c19")
    warfarin = next(item for item in summary.derived_insights if item.id == "warfarin")
    assert cyp2c19.tier == "warning"
    assert "intermediate" in cyp2c19.summary
    assert warfarin.tier == "risk"
    assert "warfarin" in warfarin.summary.lower()
