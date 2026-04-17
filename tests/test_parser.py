from pathlib import Path

from opendna.parser import parse_23andme


def test_parse_23andme_skips_comments_and_blanks(fixtures_dir: Path) -> None:
    result = parse_23andme(fixtures_dir / "sample_23andme.txt")
    assert result["rs4680"] == "GG"
    assert result["rs1801133"] == "CT"
    assert len(result) == 11


def test_parse_23andme_handles_missing_file(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        parse_23andme(tmp_path / "does-not-exist.txt")


def test_parse_23andme_ignores_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "d.txt"
    path.write_text("# header\nrs1\t1\t100\tAA\nnot-a-row\nrs2\t2\t200\tGG\n")
    result = parse_23andme(path)
    assert result == {"rs1": "AA", "rs2": "GG"}


def test_parse_23andme_preserves_no_call_genotype(fixtures_dir: Path) -> None:
    result = parse_23andme(fixtures_dir / "sample_23andme.txt")
    assert result["rs9999"] == "--"


def test_parse_23andme_accepts_string_path(fixtures_dir: Path) -> None:
    result = parse_23andme(str(fixtures_dir / "sample_23andme.txt"))
    assert "rs4680" in result
