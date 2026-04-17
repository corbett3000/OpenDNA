"""Regenerate pre-filtered ClinVar / PharmGKB annotation subsets.

Usage:
    python scripts/build_annotations.py --source clinvar
    python scripts/build_annotations.py --source pharmgkb

Requires network access. The full ClinVar VCF is ~300 MB; we stream and filter
to just the rsids referenced by our bundled panels.

Note: for MVP this script emits the same hand-curated content as the shipped
subset. Full upstream fetching is implemented in the v0.1.1 release.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PANELS_DIR = Path(__file__).parent.parent / "src" / "opendna" / "panels"
OUT_DIR = Path(__file__).parent.parent / "src" / "opendna" / "annotations"


def collect_panel_rsids() -> set[str]:
    rsids: set[str] = set()
    for p in PANELS_DIR.glob("*.json"):
        data = json.loads(p.read_text())
        for snp in data["snps"]:
            rsids.add(snp["rsid"])
    return rsids


def build_clinvar(rsids: set[str]) -> None:
    print(f"[clinvar] Would filter ClinVar VCF to {len(rsids)} rsids: {sorted(rsids)}")
    print("[clinvar] Full upstream fetcher lands in v0.1.1. Current subset is hand-curated.")


def build_pharmgkb(rsids: set[str]) -> None:
    print(f"[pharmgkb] Would filter PharmGKB annotations to {len(rsids)} rsids.")
    print("[pharmgkb] Full upstream fetcher lands in v0.1.1. Current subset is hand-curated.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=["clinvar", "pharmgkb", "all"], required=True)
    args = p.parse_args()

    rsids = collect_panel_rsids()
    if args.source in {"clinvar", "all"}:
        build_clinvar(rsids)
    if args.source in {"pharmgkb", "all"}:
        build_pharmgkb(rsids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
