"""Runtime annotation DB refresher — invoked by `opendna update-db`.

For v0.1.0 MVP this is a stub that confirms shipped data is present. v0.1.1
will fetch live upstream data.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def refresh() -> dict[str, object]:
    """Report on the currently-loaded annotation subsets."""
    clinvar_path = Path(str(files("opendna.annotations").joinpath("clinvar.json")))
    pharmgkb_path = Path(str(files("opendna.annotations").joinpath("pharmgkb.json")))
    return {
        "clinvar_path": str(clinvar_path),
        "clinvar_size_bytes": clinvar_path.stat().st_size,
        "pharmgkb_path": str(pharmgkb_path),
        "pharmgkb_size_bytes": pharmgkb_path.stat().st_size,
        "mode": "shipped-subset",
        "next": "Run `opendna update-db --online` in v0.1.1 for live upstream fetch.",
    }
