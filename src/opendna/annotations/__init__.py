"""Annotation subset loaders and join helper."""
from __future__ import annotations

import json
from functools import cache
from importlib.resources import files

from opendna.models import Finding


@cache
def load_clinvar() -> dict[str, dict]:
    raw = files("opendna.annotations").joinpath("clinvar.json").read_text()
    return json.loads(raw)


@cache
def load_pharmgkb() -> dict[str, dict]:
    raw = files("opendna.annotations").joinpath("pharmgkb.json").read_text()
    return json.loads(raw)


def annotate(
    findings: list[Finding],
    clinvar: dict[str, dict],
    pharmgkb: dict[str, dict],
) -> list[Finding]:
    """Attach ClinVar + PharmGKB entries to each finding (returns new list)."""
    out: list[Finding] = []
    for f in findings:
        clinvar_entry = clinvar.get(f.rsid)
        pgkb_entry = pharmgkb.get(f.rsid)
        out.append(
            f.model_copy(
                update={
                    "clinvar": clinvar_entry,
                    "pharmgkb": pgkb_entry["recommendations"] if pgkb_entry else None,
                }
            )
        )
    return out
