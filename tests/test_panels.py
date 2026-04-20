from opendna.panels import load_panels

EXPECTED_PANELS = {
    "methylation",
    "cardiovascular",
    "pharmacogenomics",
    "athletic",
    "dietary",
    "eye_health",
    "hfe",
    "histamine",
    "cognition",
    "nicotine",
    "sensitivity",
    "vitamin_d",
}


def test_all_twelve_panels_load() -> None:
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
    eye_rsids = {s.rsid for s in panels["eye_health"].snps}
    histamine_rsids = {s.rsid for s in panels["histamine"].snps}
    nicotine_rsids = {s.rsid for s in panels["nicotine"].snps}
    vitamin_d_rsids = {s.rsid for s in panels["vitamin_d"].snps}
    assert "rs6025" in cardio_rsids   # F5 Factor V Leiden
    assert "rs1799963" in cardio_rsids  # F2 prothrombin G20210A
    assert "rs2108622" in pgx_rsids  # CYP4F2 warfarin modifier
    assert "rs2231142" in pgx_rsids  # ABCG2 statin transporter
    assert "rs3918290" in pgx_rsids  # DPYD *2A
    assert "rs1061170" in eye_rsids  # CFH Y402H
    assert "rs10490924" in eye_rsids  # ARMS2 A69S
    assert "rs10156191" in histamine_rsids  # AOC1 / DAO
    assert "rs11558538" in histamine_rsids  # HNMT
    assert "rs16969968" in nicotine_rsids  # CHRNA5
    assert "rs12785878" in vitamin_d_rsids  # DHCR7


def test_snp_interpretations_are_indexed_by_genotype() -> None:
    panels = {p.id: p for p in load_panels()}
    mthfr = next(s for s in panels["methylation"].snps if s.rsid == "rs1801133")
    assert "CC" in mthfr.interpretations
    assert mthfr.interpretations["CC"].tier in {"normal", "warning", "risk"}
