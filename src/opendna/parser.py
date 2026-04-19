"""23andMe-style raw DNA file parser."""
from __future__ import annotations

from pathlib import Path

from opendna.models import ParseIssue, ParseResult, SourceFileInfo

_VENDOR_PATTERNS = {
    "23andMe": ("23andme", "23and me", "fileformat=23andme"),
    "AncestryDNA": ("ancestrydna", "ancestry dna"),
    "MyHeritage": ("myheritage",),
    "FTDNA": ("ftdna", "family tree dna", "myftdna"),
}

_VENDOR_BLIND_SPOTS = {
    "23andMe": [
        "Chip versions vary, so absent markers often reflect array design rather "
        "than a true negative result.",
        "This file is good for common SNPs but still misses rare variants, "
        "structural variants, and most CYP2D6/HLA haplotypes.",
    ],
    "AncestryDNA": [
        "Absent pharmacogenomic markers often reflect chip design, not biology.",
        "Common SNP coverage is useful, but rare pathogenic variants and "
        "structural changes remain invisible.",
    ],
    "MyHeritage": [
        "Coverage is strongest for common SNPs; niche pharmacogenomic markers are patchier.",
        "Rare variants, structural variants, and haplotype calls still require sequencing data.",
    ],
    "FTDNA": [
        "A missing rsid here should be read as vendor omission, not a negative genotype.",
        "This file cannot resolve structural variants, copy-number changes, or "
        "most star-allele haplotypes.",
    ],
}

_GENERIC_BLIND_SPOTS = [
    "Consumer array files only assay a tiny fraction of the genome, so normal "
    "here never rules out other variants in the same gene.",
    "This file type does not support rare-variant calling, structural variants, "
    "methylation, HLA typing, or most CYP2D6 star-allele inference.",
]

_NO_CALL_GENOTYPES = {"--", "-", "00", "NN", "NC"}


def _detect_vendor(comment_lines: list[str], file_name: str) -> str | None:
    haystack = "\n".join(comment_lines + [file_name]).lower()
    for vendor, patterns in _VENDOR_PATTERNS.items():
        if any(pattern in haystack for pattern in patterns):
            return vendor
    return None


def _detect_build(comment_lines: list[str]) -> str | None:
    haystack = "\n".join(comment_lines).lower()
    if "grch38" in haystack or "build 38" in haystack:
        return "GRCh38"
    if "grch37" in haystack or "build 37" in haystack:
        return "GRCh37"
    return None


def _classify_genotype(genotype: str) -> str:
    if genotype in _NO_CALL_GENOTYPES:
        return "no_call"
    if not genotype:
        return "ambiguous"
    if any(base not in "ACGT" for base in genotype):
        return "ambiguous"
    if len(genotype) not in {1, 2}:
        return "ambiguous"
    return "called"


def _build_issues(
    unique_rsid_count: int,
    malformed_row_count: int,
    duplicate_rsid_count: int,
    no_call_count: int,
    ambiguous_call_count: int,
    vendor: str | None,
    build: str | None,
) -> list[ParseIssue]:
    issues: list[ParseIssue] = []
    if unique_rsid_count < 50_000:
        issues.append(
            ParseIssue(
                severity="warning",
                code="small-file",
                message=(
                    "This raw DNA file is unusually small. Treat absent markers very cautiously; "
                    "the file may be truncated or heavily filtered."
                ),
            )
        )
    if malformed_row_count:
        issues.append(
            ParseIssue(
                severity="warning",
                code="malformed-rows",
                message=f"Skipped {malformed_row_count} malformed rows while parsing the file.",
            )
        )
    if duplicate_rsid_count:
        issues.append(
            ParseIssue(
                severity="warning",
                code="duplicate-rsids",
                message=(
                    f"Found {duplicate_rsid_count} duplicate rsids. The last occurrence was kept "
                    "for analysis."
                ),
            )
        )
    if no_call_count:
        issues.append(
            ParseIssue(
                severity="info",
                code="no-calls",
                message=(
                    f"{no_call_count} markers were present in the file but had no "
                    "confident genotype call."
                ),
            )
        )
    if ambiguous_call_count:
        issues.append(
            ParseIssue(
                severity="warning",
                code="ambiguous-calls",
                message=(
                    f"{ambiguous_call_count} markers used a non-standard genotype format and were "
                    "not treated as high-confidence calls."
                ),
            )
        )
    if vendor is None:
        issues.append(
            ParseIssue(
                severity="info",
                code="vendor-unknown",
                message="Vendor could not be identified heuristically from the file header.",
            )
        )
    if build is None:
        issues.append(
            ParseIssue(
                severity="info",
                code="build-unknown",
                message="Reference build was not detected from the file header.",
            )
        )
    return issues


def parse_source_file(path: Path | str) -> ParseResult:
    """Parse a consumer-DNA TSV into genotypes plus file-level metadata."""
    path = Path(path)
    results: dict[str, str] = {}
    comment_lines: list[str] = []
    chromosomes: set[str] = set()
    parsed_row_count = 0
    malformed_row_count = 0
    duplicate_rsid_count = 0
    no_call_count = 0
    ambiguous_call_count = 0

    with path.open(encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                comment_lines.append(line)
                continue

            parts = line.split("\t")
            if len(parts) < 4:
                malformed_row_count += 1
                continue

            rsid, chrom, _pos, genotype = parts[:4]
            if not rsid.startswith("rs"):
                malformed_row_count += 1
                continue

            parsed_row_count += 1
            chromosomes.add(chrom)
            genotype = genotype.strip().upper()
            if rsid in results:
                duplicate_rsid_count += 1
            results[rsid] = genotype

            status = _classify_genotype(genotype)
            if status == "no_call":
                no_call_count += 1
            elif status == "ambiguous":
                ambiguous_call_count += 1

    vendor = _detect_vendor(comment_lines, path.name)
    build = _detect_build(comment_lines)
    issues = _build_issues(
        unique_rsid_count=len(results),
        malformed_row_count=malformed_row_count,
        duplicate_rsid_count=duplicate_rsid_count,
        no_call_count=no_call_count,
        ambiguous_call_count=ambiguous_call_count,
        vendor=vendor,
        build=build,
    )
    blind_spots = _GENERIC_BLIND_SPOTS + _VENDOR_BLIND_SPOTS.get(vendor, [])
    return ParseResult(
        genotypes=results,
        source=SourceFileInfo(
            path=str(path),
            vendor=vendor,
            build=build,
            unique_rsid_count=len(results),
            parsed_row_count=parsed_row_count,
            malformed_row_count=malformed_row_count,
            duplicate_rsid_count=duplicate_rsid_count,
            no_call_count=no_call_count,
            ambiguous_call_count=ambiguous_call_count,
            comment_line_count=len(comment_lines),
            chromosome_labels=sorted(chromosomes),
            blind_spots=blind_spots,
            issues=issues,
        ),
    )


def parse_23andme(path: Path | str) -> dict[str, str]:
    """Parse a 23andMe-format TSV into {rsid: genotype}.

    Lines starting with '#' are treated as comments. Malformed rows are
    silently skipped — upstream providers occasionally ship corrupt lines.
    """
    return parse_source_file(path).genotypes
