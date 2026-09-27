"""Tests for MyHeritage CSV format parsing and end-to-end analysis pipeline.

The fixture ``tests/fixtures/myheritage_sample.csv`` is derived from the
``tests/test-dna.csv`` sample provided with the project. It uses the
MyHeritage raw-data format:

  - Comment / metadata lines prefixed with ``#`` or ``##``
  - A CSV header row: ``RSID,CHROMOSOME,POSITION,RESULT``
  - Data rows with double-quoted fields, e.g. ``"rs1801133","1","11856378","CT"``

These tests verify that the parser handles the CSV format correctly and that
the analysis pipeline produces accurate findings that can be exported to JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from opendna.analyzer import analyze
from opendna.panels import load_panels
from opendna.parser import parse_23andme, parse_source_file


# ---------------------------------------------------------------------------
# Parser — CSV format detection & field extraction
# ---------------------------------------------------------------------------


class TestMyHeritageCsvParsing:
    """parse_source_file correctly reads MyHeritage CSV-format raw DNA files."""

    def test_detects_myheritage_vendor(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.source.vendor == "MyHeritage"

    def test_detects_grch37_build_from_reference_field(self, fixtures_dir: Path) -> None:
        """##reference=build37 (no space) should be mapped to GRCh37."""
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.source.build == "GRCh37"

    def test_extracts_quoted_rsids(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert "rs1801133" in result.genotypes
        assert "rs4680" in result.genotypes

    def test_strips_quotes_from_genotype(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        # Genotype values must not contain surrounding quotes.
        for genotype in result.genotypes.values():
            assert not genotype.startswith('"'), f"Quoted genotype leaked: {genotype!r}"

    def test_genotypes_are_uppercased(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        for genotype in result.genotypes.values():
            assert genotype == genotype.upper()

    def test_header_row_not_counted_as_malformed(self, fixtures_dir: Path) -> None:
        """The RSID/CHROMOSOME/POSITION/RESULT header must be skipped silently."""
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.source.malformed_row_count == 0

    def test_comment_lines_counted(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        # The fixture has 12 comment lines (## and # lines).
        assert result.source.comment_line_count == 12

    def test_correct_unique_rsid_count(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.source.unique_rsid_count == 8

    def test_correct_parsed_row_count(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.source.parsed_row_count == 8

    def test_specific_genotype_values(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert result.genotypes["rs1801133"] == "CT"
        assert result.genotypes["rs4680"] == "GG"
        assert result.genotypes["rs6265"] == "TT"
        assert result.genotypes["rs9000001"] == "GA"
        assert result.genotypes["rs9000002"] == "GG"

    def test_chromosome_labels_extracted(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert "1" in result.source.chromosome_labels
        assert "22" in result.source.chromosome_labels

    def test_blind_spots_include_myheritage_notes(self, fixtures_dir: Path) -> None:
        result = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        assert any("MyHeritage" in note or "coverage" in note.lower()
                   for note in result.source.blind_spots), \
            "Expected MyHeritage-specific blind-spot notes"

    def test_parse_23andme_compat_alias_works_on_csv(self, fixtures_dir: Path) -> None:
        """parse_23andme() is a thin alias — it should work on CSV files too."""
        genotypes = parse_23andme(fixtures_dir / "myheritage_sample.csv")
        assert "rs1801133" in genotypes
        assert genotypes["rs1801133"] == "CT"


class TestBuildDetectionVariants:
    """Build-reference detection handles both spaced and non-spaced patterns."""

    def test_build37_no_space(self, tmp_path: Path) -> None:
        path = tmp_path / "dna.csv"
        path.write_text("## reference=build37\nRSID,CHR,POS,RESULT\nrs1,1,100,AA\n")
        result = parse_source_file(path)
        assert result.source.build == "GRCh37"

    def test_build38_no_space(self, tmp_path: Path) -> None:
        path = tmp_path / "dna.csv"
        path.write_text("## reference=build38\nRSID,CHR,POS,RESULT\nrs1,1,100,AA\n")
        result = parse_source_file(path)
        assert result.source.build == "GRCh38"

    def test_build_37_with_space(self, tmp_path: Path) -> None:
        path = tmp_path / "dna.txt"
        path.write_text("# Reference Human Assembly Build 37\nrs1\t1\t100\tAA\n")
        result = parse_source_file(path)
        assert result.source.build == "GRCh37"


class TestCsvVsTsvAutoDetection:
    """Parser auto-detects the delimiter: commas → CSV, tabs → TSV."""

    def test_csv_delimiter_detected(self, tmp_path: Path) -> None:
        path = tmp_path / "csv.csv"
        path.write_text('RSID,CHR,POS,RESULT\n"rs1801133","1","11856378","CT"\n')
        result = parse_source_file(path)
        assert result.genotypes.get("rs1801133") == "CT"

    def test_tsv_delimiter_still_works(self, tmp_path: Path) -> None:
        path = tmp_path / "tsv.txt"
        path.write_text("# header\nrs1801133\t1\t11856378\tCT\n")
        result = parse_source_file(path)
        assert result.genotypes.get("rs1801133") == "CT"

    def test_csv_without_quotes(self, tmp_path: Path) -> None:
        """Unquoted CSV fields should also be parsed correctly."""
        path = tmp_path / "plain.csv"
        path.write_text("RSID,CHR,POS,RESULT\nrs4680,22,19951271,GG\n")
        result = parse_source_file(path)
        assert result.genotypes.get("rs4680") == "GG"


# ---------------------------------------------------------------------------
# Analyzer — findings from MyHeritage CSV genotypes
# ---------------------------------------------------------------------------


class TestAnalyzerWithMyHeritageData:
    """analyze() produces correct findings when fed genotypes from a CSV file."""

    @pytest.fixture
    def parsed(self, fixtures_dir: Path):
        return parse_source_file(fixtures_dir / "myheritage_sample.csv")

    @pytest.fixture
    def findings(self, parsed):
        return analyze(parsed.genotypes, load_panels())

    def test_mthfr_rs1801133_ct_is_warning(self, findings) -> None:
        hit = next(
            (f for f in findings if f.rsid == "rs1801133" and f.panel_id == "methylation"),
            None,
        )
        assert hit is not None, "rs1801133 finding not found in methylation panel"
        assert hit.genotype == "CT"
        assert hit.tier == "warning"
        assert hit.call_status == "called"
        assert hit.confidence_label == "high"

    def test_comt_rs4680_gg_is_warning(self, findings) -> None:
        hit = next(
            (f for f in findings if f.rsid == "rs4680" and f.panel_id == "methylation"),
            None,
        )
        assert hit is not None
        assert hit.genotype == "GG"
        assert hit.tier == "warning"

    def test_bdnf_rs6265_tt_is_risk(self, findings) -> None:
        hit = next(
            (f for f in findings if f.rsid == "rs6265" and f.panel_id == "cognition"),
            None,
        )
        assert hit is not None
        assert hit.tier == "risk"

    def test_actn3_rs1815739_ct_is_normal(self, findings) -> None:
        hit = next(
            (f for f in findings if f.rsid == "rs1815739" and f.panel_id == "athletic"),
            None,
        )
        assert hit is not None
        assert hit.tier == "normal"

    def test_generic_snps_not_matched_in_panels(self, findings) -> None:
        """rs9000001 and rs9000002 are not in any panel — not_tested expected."""
        for rsid in ("rs9000001", "rs9000002"):
            matched = [f for f in findings if f.rsid == rsid and f.call_status == "called"]
            assert matched == [], f"{rsid} should not have a called finding in any panel"

    def test_all_called_findings_have_high_confidence(self, findings) -> None:
        called = [f for f in findings if f.call_status == "called"]
        assert called, "Expected at least some called findings"
        for f in called:
            assert f.confidence_score > 0
            assert f.confidence_label in {"high", "medium"}


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


class TestJsonExport:
    """Findings from the MyHeritage CSV fixture can be serialised to valid JSON."""

    @pytest.fixture
    def findings(self, fixtures_dir: Path):
        parsed = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        return analyze(parsed.genotypes, load_panels())

    def test_findings_serialise_to_valid_json(self, findings) -> None:
        payload = [f.model_dump() for f in findings]
        raw = json.dumps(payload)
        decoded = json.loads(raw)
        assert isinstance(decoded, list)
        assert len(decoded) == len(findings)

    def test_json_contains_rsid_and_tier_fields(self, findings) -> None:
        payload = json.loads(json.dumps([f.model_dump() for f in findings]))
        for item in payload:
            assert "rsid" in item
            assert "tier" in item
            assert "panel_id" in item

    def test_json_called_findings_have_genotype(self, findings) -> None:
        called = [f.model_dump() for f in findings if f.call_status == "called"]
        for item in called:
            assert item["genotype"] is not None
            assert len(item["genotype"]) in {1, 2}

    def test_json_export_to_file(self, findings, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        payload = [f.model_dump() for f in findings]
        out.write_text(json.dumps(payload, indent=2))
        loaded = json.loads(out.read_text())
        assert len(loaded) == len(findings)

    def test_json_includes_source_file_info(self, fixtures_dir: Path) -> None:
        parsed = parse_source_file(fixtures_dir / "myheritage_sample.csv")
        source_dict = parsed.source.model_dump()
        raw = json.dumps(source_dict)
        decoded = json.loads(raw)
        assert decoded["vendor"] == "MyHeritage"
        assert decoded["build"] == "GRCh37"
        assert decoded["unique_rsid_count"] == 8
