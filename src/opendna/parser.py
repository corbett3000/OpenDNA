"""23andMe-style raw DNA file parser."""
from __future__ import annotations

from pathlib import Path


def parse_23andme(path: Path | str) -> dict[str, str]:
    """Parse a 23andMe-format TSV into {rsid: genotype}.

    Lines starting with '#' are treated as comments. Malformed rows are
    silently skipped — upstream providers occasionally ship corrupt lines.
    """
    path = Path(path)
    results: dict[str, str] = {}
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            rsid, _chrom, _pos, genotype = parts[:4]
            if rsid.startswith("rs"):
                results[rsid] = genotype
    return results
