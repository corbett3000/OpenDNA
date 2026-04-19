from opendna.analyzer import analyze
from opendna.panels import load_panels


def test_analyze_returns_finding_per_panel_snp() -> None:
    panels = load_panels()
    parsed = {"rs1801133": "CT", "rs4680": "GG"}
    findings = analyze(parsed, panels)
    rsids = {(f.panel_id, f.rsid) for f in findings}
    assert ("methylation", "rs1801133") in rsids
    assert ("methylation", "rs4680") in rsids


def test_analyze_marks_missing_snps_as_unknown() -> None:
    panels = [p for p in load_panels() if p.id == "methylation"]
    parsed: dict[str, str] = {}
    findings = analyze(parsed, panels)
    missing = [f for f in findings if f.rsid == "rs1801133"]
    assert len(missing) == 1
    assert missing[0].genotype is None
    assert missing[0].tier == "unknown"


def test_analyze_uses_interpretation_for_known_genotype() -> None:
    panels = [p for p in load_panels() if p.id == "methylation"]
    findings = analyze({"rs1801133": "TT"}, panels)
    hit = next(f for f in findings if f.rsid == "rs1801133")
    assert hit.tier == "risk"
    assert hit.genotype == "TT"


def test_analyze_handles_reverse_strand_genotype() -> None:
    """Some files report genotypes on reverse strand (e.g. AG vs GA)."""
    panels = [p for p in load_panels() if p.id == "methylation"]
    findings = analyze({"rs1801131": "CA"}, panels)
    hit = next(f for f in findings if f.rsid == "rs1801131")
    # Panel defines "AC"; "CA" should resolve to the same interpretation.
    assert hit.tier == "warning"


def test_analyze_filters_by_panel_ids() -> None:
    panels = load_panels()
    findings = analyze({"rs1815739": "CT"}, panels, selected_panel_ids={"athletic"})
    assert all(f.panel_id == "athletic" for f in findings)
    assert any(f.rsid == "rs1815739" for f in findings)


def test_analyze_handles_reverse_complement_genotype() -> None:
    """User file reports opposite strand: panel 'CC' matches user 'GG' for C/T SNPs."""
    panels = [p for p in load_panels() if p.id == "methylation"]
    # MTHFR rs1801133 panel: CC=normal, CT=warning, TT=risk (C/T SNP — not palindromic).
    # A file reporting the reverse strand would show GG/GA/AA.
    findings = analyze({"rs1801133": "GG"}, panels)
    hit = next(f for f in findings if f.rsid == "rs1801133")
    assert hit.tier == "normal"   # GG → RC → CC → normal
    assert hit.genotype == "GG"   # preserve the raw genotype in the finding
    assert hit.interpreted_genotype == "CC"
    assert hit.match_method == "reverse_complement"
    assert hit.confidence_label == "high"

    findings = analyze({"rs1801133": "AA"}, panels)
    hit = next(f for f in findings if f.rsid == "rs1801133")
    assert hit.tier == "risk"     # AA → RC → TT → risk
    assert hit.interpreted_genotype == "TT"


def test_analyze_skips_reverse_complement_for_palindromic_sites() -> None:
    """A/T-only and C/G-only SNPs are palindromic; RC is unreliable there."""
    from opendna.models import Interpretation, Panel, SnpDef

    # Synthetic panel with an A/T-only SNP (palindromic).
    palindromic_panel = Panel(
        id="palindromic_test",
        name="Test Palindromic",
        description="A/T-only site — RC collides with forward strand.",
        snps=[
            SnpDef(
                rsid="rs9000001",
                gene="FAKE",
                variant_name="palindrome",
                description="test",
                interpretations={
                    "AA": Interpretation(tier="normal", note="normal"),
                    "AT": Interpretation(tier="warning", note="warn"),
                    "TT": Interpretation(tier="risk", note="risk"),
                },
            )
        ],
    )
    # User reports "CC" — not in panel. Panel is palindromic (only A/T alleles).
    # RC of CC is GG, which is also not in the panel. Must remain unknown.
    findings = analyze({"rs9000001": "CC"}, [palindromic_panel])
    assert len(findings) == 1
    assert findings[0].tier == "unknown"


def test_analyze_marks_no_calls_explicitly() -> None:
    panels = [p for p in load_panels() if p.id == "methylation"]
    findings = analyze({"rs1801133": "--"}, panels)
    hit = next(f for f in findings if f.rsid == "rs1801133")
    assert hit.call_status == "no_call"
    assert hit.match_method == "no_call"
    assert hit.confidence_score == 0
    assert hit.tier == "unknown"
