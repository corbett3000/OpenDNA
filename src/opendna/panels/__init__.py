"""Panel loader — reads all *.json panels shipped with the package."""
from __future__ import annotations

import json
from functools import cache
from importlib.resources import files

from opendna.models import Panel


@cache
def load_panels() -> list[Panel]:
    """Return every bundled panel, sorted by id."""
    pkg = files("opendna.panels")
    panels: list[Panel] = []
    for entry in pkg.iterdir():
        if entry.name.endswith(".json"):
            data = json.loads(entry.read_text())
            panels.append(Panel.model_validate(data))
    panels.sort(key=lambda p: p.id)
    return panels
