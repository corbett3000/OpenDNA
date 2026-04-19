from opendna.panels import load_panels

EXPECTED_PANELS = {
    "methylation",
    "cardiovascular",
    "pharmacogenomics",
    "athletic",
    "dietary",
    "hfe",
    "cognition",
    "sensitivity",
}


def test_all_eight_panels_load() -> None:
    panels = load_panels()
    assert {p.id for p in panels} == EXPECTED_PANELS


def test_every_panel_has_at_least_three_snps() -> None:
    for p in load_panels():
        assert len(p.snps) >= 3, f"{p.id} has too few SNPs"


def test_every_snp_has_interpretations_for_multiple_genotypes() -> None:
    for p in load_panels():
        for snp in p.snps:
            assert len(snp.interpretations) >= 2, f"{snp.rsid} in {p.id} lacks interpretations"


def test_methylation_panel_has_known_snps() -> None:
    panels = {p.id: p for p in load_panels()}
    methylation = panels["methylation"]
    rsids = {s.rsid for s in methylation.snps}
    assert "rs1801133" in rsids  # MTHFR C677T
    assert "rs4680" in rsids     # COMT


def test_expanded_panels_include_new_high_signal_markers() -> None:
    panels = {p.id: p for p in load_panels()}
    cardio_rsids = {s.rsid for s in panels["cardiovascular"].snps}
    pgx_rsids = {s.rsid for s in panels["pharmacogenomics"].snps}
    assert "rs6025" in cardio_rsids   # F5 Factor V Leiden
    assert "rs1799963" in cardio_rsids  # F2 prothrombin G20210A
    assert "rs2108622" in pgx_rsids  # CYP4F2 warfarin modifier


def test_snp_interpretations_are_indexed_by_genotype() -> None:
    panels = {p.id: p for p in load_panels()}
    mthfr = next(s for s in panels["methylation"].snps if s.rsid == "rs1801133")
    assert "CC" in mthfr.interpretations
    assert mthfr.interpretations["CC"].tier in {"normal", "warning", "risk"}
