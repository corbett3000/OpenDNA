from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.models import Finding


def test_load_clinvar_returns_dict_keyed_by_rsid() -> None:
    data = load_clinvar()
    assert isinstance(data, dict)
    assert "rs1142345" in data  # TPMT *3C
    assert data["rs1142345"]["clinical_significance"]


def test_load_pharmgkb_returns_dict_keyed_by_rsid() -> None:
    data = load_pharmgkb()
    assert "rs1142345" in data
    entry = data["rs1142345"]
    assert "recommendations" in entry


def test_annotate_adds_clinvar_and_pharmgkb_to_findings() -> None:
    findings = [
        Finding(
            panel_id="pharmacogenomics",
            rsid="rs1142345",
            gene="TPMT",
            genotype="TT",
            tier="risk",
            note="Poor metabolizer",
            description="Thiopurine metabolism",
        )
    ]
    annotated = annotate(findings, load_clinvar(), load_pharmgkb())
    assert annotated[0].clinvar is not None
    assert annotated[0].pharmgkb is not None
    assert len(annotated[0].pharmgkb) >= 1


def test_annotate_leaves_unknown_rsids_untouched() -> None:
    findings = [
        Finding(
            panel_id="test",
            rsid="rs9999999999",
            gene="TEST",
            genotype="AA",
            tier="unknown",
            note="",
            description="",
        )
    ]
    annotated = annotate(findings, load_clinvar(), load_pharmgkb())
    assert annotated[0].clinvar is None
    assert annotated[0].pharmgkb is None
