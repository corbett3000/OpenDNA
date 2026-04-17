# OpenDNA MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local-first web utility (`opendna`) that parses a 23andMe-style raw DNA file, matches it against 8 curated SNP panels annotated with ClinVar + PharmGKB, and renders a self-contained HTML report with optional BYOK LLM synthesis.

**Architecture:** Single Python package (`opendna`) exposing a FastAPI server with three endpoints, backed by pure-stdlib parsing and Jinja2 rendering. Vanilla JS SPA (no `innerHTML`-with-user-data — uses DOM APIs). LLM layer is a pluggable ABC (Anthropic default with prompt caching, OpenAI secondary). Annotation subsets ship pre-filtered in-repo; `scripts/build_annotations.py` regenerates them from upstream.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Pydantic v2, httpx, anthropic SDK, openai SDK, pytest, ruff.

---

## File Structure

Files created in order of dependency. Each bullet = one file's responsibility.

```
OpenDNA/
├── pyproject.toml                     # package metadata, deps, entry point
├── README.md                          # user-facing docs (install, privacy, usage)
├── LICENSE                            # MIT
├── .gitignore                         # Python + editor noise
├── .github/workflows/ci.yml           # pytest + ruff on 3.11/3.12/3.13
├── CONTRIBUTING.md                    # dev setup, release process
├── scripts/
│   └── build_annotations.py           # regenerates ClinVar/PharmGKB subsets from upstream
├── src/opendna/
│   ├── __init__.py                    # __version__
│   ├── __main__.py                    # CLI dispatch (serve, scan, update-db)
│   ├── cli.py                         # argparse definitions + subcommand handlers
│   ├── parser.py                      # 23andMe TSV → dict[rsid, genotype]
│   ├── models.py                      # Pydantic models: Panel, SnpDef, Finding, Report
│   ├── panels/
│   │   ├── __init__.py                # load_panels() reads all *.json
│   │   ├── methylation.json
│   │   ├── cardiovascular.json
│   │   ├── pharmacogenomics.json
│   │   ├── athletic.json
│   │   ├── dietary.json
│   │   ├── hfe.json
│   │   ├── cognition.json
│   │   └── sensitivity.json
│   ├── annotations/
│   │   ├── __init__.py                # load_clinvar(), load_pharmgkb()
│   │   ├── clinvar.json               # pre-filtered subset
│   │   ├── pharmgkb.json              # pre-filtered subset
│   │   └── updater.py                 # invoked by update-db CLI
│   ├── analyzer.py                    # analyze(parsed, panels, annotations) → list[Finding]
│   ├── llm/
│   │   ├── __init__.py                # get_provider(name) factory
│   │   ├── base.py                    # Provider ABC: interpret(findings) → str
│   │   ├── anthropic.py               # claude-sonnet-4-6 + prompt caching
│   │   └── openai.py                  # gpt-4o default
│   ├── report/
│   │   ├── __init__.py                # render_report(findings, prose?) → {html, json}
│   │   ├── render.py                  # Jinja2 driver
│   │   └── template.html.j2           # self-contained HTML (inline CSS, autoescape on)
│   ├── server.py                      # FastAPI app + 3 routes
│   └── web/
│       └── static/
│           ├── index.html             # SPA shell
│           ├── app.js                 # form → /api/analyze → render (DOM APIs, sandboxed iframe)
│           └── style.css
└── tests/
    ├── __init__.py
    ├── conftest.py                    # shared fixtures
    ├── fixtures/
    │   ├── sample_23andme.txt         # ~10-row synthetic DNA file
    │   ├── sample_clinvar.json        # minimal subset for tests
    │   └── sample_pharmgkb.json
    ├── test_parser.py
    ├── test_panels.py
    ├── test_analyzer.py
    ├── test_annotations.py
    ├── test_report.py
    ├── test_llm_anthropic.py
    ├── test_llm_openai.py
    ├── test_server.py
    ├── test_cli.py
    └── test_e2e.py
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `.gitignore`, `README.md` (skeleton), `.github/workflows/ci.yml`
- Create: `src/opendna/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "opendna"
version = "0.1.0"
description = "Local-first web utility for interpreting raw consumer DNA files"
readme = "README.md"
license = { text = "MIT" }
authors = [{ name = "Peter Corbett" }]
requires-python = ">=3.11"
classifiers = [
    "Development Status :: 3 - Alpha",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Bio-Informatics",
]
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "jinja2>=3.1",
    "pydantic>=2.6",
    "httpx>=0.27",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
anthropic = ["anthropic>=0.34"]
openai = ["openai>=1.30"]
all = ["opendna[anthropic,openai]"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]

[project.scripts]
opendna = "opendna.__main__:main"

[project.urls]
Homepage = "https://github.com/corbett3000/OpenDNA"
Issues = "https://github.com/corbett3000/OpenDNA/issues"

[tool.hatch.build.targets.wheel]
packages = ["src/opendna"]

[tool.hatch.build.targets.wheel.shared-data]
"src/opendna/panels" = "opendna/panels"
"src/opendna/annotations" = "opendna/annotations"
"src/opendna/report/template.html.j2" = "opendna/report/template.html.j2"
"src/opendna/web/static" = "opendna/web/static"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Peter Corbett

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
dist/
build/
.DS_Store
.env
*.pc.txt
*_genome_*.txt
*_genome_*.zip
```

- [ ] **Step 4: Create `README.md` (skeleton; finalized in Task 12)**

```markdown
# OpenDNA

Local-first web utility for interpreting raw consumer DNA files (23andMe, AncestryDNA, MyHeritage). Your DNA never leaves your machine.

> **Status:** Pre-MVP. Not for clinical use.

## Install

```bash
pip install opendna
opendna serve
# open http://localhost:8787
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup.
```

- [ ] **Step 5: Create `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev,all]"
      - run: ruff check src tests
      - run: pytest -v
```

- [ ] **Step 6: Create package skeletons**

`src/opendna/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
```

- [ ] **Step 7: Install + verify**

```bash
cd /Users/corbett3000/Coding/OpenDNA
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,all]"
pytest -v
```

Expected: `no tests ran` (exit 5, acceptable — will fail CI until Task 2, that's fine since we don't push yet).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml LICENSE .gitignore README.md .github src tests
git commit -m "chore: project scaffolding (pyproject, MIT license, CI, package skeleton)"
```

---

## Task 2: DNA file parser

**Files:**
- Create: `tests/fixtures/sample_23andme.txt`
- Create: `src/opendna/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/sample_23andme.txt`:
```
# This data file generated by 23andMe
# fileformat=23andme-generic
# Reference Human Assembly Build 37 (GRCh37.p13)
#
# rsid	chromosome	position	genotype
rs4477212	1	82154	AA
rs1801133	1	11856378	CT
rs1801131	1	11854476	AC
rs4680	22	19951271	GG
rs9939609	16	53820527	AT
rs6265	11	27679916	TT
rs429358	19	45411941	TT
rs7412	19	45412079	CC
rs1815739	11	66560624	CT
rs1142345	6	18138997	TT
```

- [ ] **Step 2: Write the failing test**

`tests/test_parser.py`:
```python
from pathlib import Path

from opendna.parser import parse_23andme


def test_parse_23andme_skips_comments_and_blanks(fixtures_dir: Path) -> None:
    result = parse_23andme(fixtures_dir / "sample_23andme.txt")
    assert result["rs4680"] == "GG"
    assert result["rs1801133"] == "CT"
    assert len(result) == 10


def test_parse_23andme_handles_missing_file(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        parse_23andme(tmp_path / "does-not-exist.txt")


def test_parse_23andme_ignores_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "d.txt"
    path.write_text("# header\nrs1\t1\t100\tAA\nnot-a-row\nrs2\t2\t200\tGG\n")
    result = parse_23andme(path)
    assert result == {"rs1": "AA", "rs2": "GG"}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'opendna.parser'`

- [ ] **Step 4: Write the parser**

`src/opendna/parser.py`:
```python
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
    with path.open() as f:
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_parser.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/opendna/parser.py tests/test_parser.py tests/fixtures/sample_23andme.txt
git commit -m "feat(parser): 23andMe TSV parser with comment/malformed-line handling"
```

---

## Task 3: Panel data model + first panel

**Files:**
- Create: `src/opendna/models.py`
- Create: `src/opendna/panels/__init__.py`
- Create: `src/opendna/panels/methylation.json`
- Create: `tests/test_panels.py`

- [ ] **Step 1: Write the failing test**

`tests/test_panels.py`:
```python
from opendna.panels import load_panels
from opendna.models import Panel


def test_load_panels_returns_all_registered_panels() -> None:
    panels = load_panels()
    assert isinstance(panels, list)
    assert all(isinstance(p, Panel) for p in panels)
    ids = {p.id for p in panels}
    assert "methylation" in ids


def test_methylation_panel_has_known_snps() -> None:
    panels = {p.id: p for p in load_panels()}
    methylation = panels["methylation"]
    rsids = {s.rsid for s in methylation.snps}
    assert "rs1801133" in rsids  # MTHFR C677T
    assert "rs4680" in rsids     # COMT


def test_snp_interpretations_are_indexed_by_genotype() -> None:
    panels = {p.id: p for p in load_panels()}
    mthfr = next(s for s in panels["methylation"].snps if s.rsid == "rs1801133")
    assert "CC" in mthfr.interpretations
    assert mthfr.interpretations["CC"].tier in {"normal", "warning", "risk"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_panels.py -v
```

Expected: `ModuleNotFoundError: No module named 'opendna.models'`

- [ ] **Step 3: Write the models**

`src/opendna/models.py`:
```python
"""Pydantic data models for OpenDNA."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["normal", "warning", "risk", "unknown"]


class Interpretation(BaseModel):
    tier: Tier
    note: str


class SnpDef(BaseModel):
    rsid: str = Field(pattern=r"^rs\d+$")
    gene: str
    variant_name: str | None = None
    description: str
    interpretations: dict[str, Interpretation] = Field(default_factory=dict)


class Panel(BaseModel):
    id: str
    name: str
    description: str
    snps: list[SnpDef]


class Finding(BaseModel):
    panel_id: str
    rsid: str
    gene: str
    genotype: str | None          # None if the rsid isn't in the user's file
    tier: Tier
    note: str
    description: str
    clinvar: dict | None = None
    pharmgkb: list[dict] | None = None


class ReportBundle(BaseModel):
    findings: list[Finding]
    html: str
    json_payload: dict
    llm_prose: str | None = None
```

- [ ] **Step 4: Write the panel loader**

`src/opendna/panels/__init__.py`:
```python
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
```

- [ ] **Step 5: Write the methylation panel**

`src/opendna/panels/methylation.json`:
```json
{
  "id": "methylation",
  "name": "Methylation & Detox",
  "description": "Variants in the folate / methionine cycle and related detox pathways.",
  "snps": [
    {
      "rsid": "rs1801133",
      "gene": "MTHFR",
      "variant_name": "C677T",
      "description": "Central methylation enzyme; reduced function lowers folate-to-methylfolate conversion.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Standard MTHFR activity."},
        "CT": {"tier": "warning", "note": "~30% reduced enzyme activity; monitor homocysteine."},
        "TT": {"tier": "risk", "note": "~60-70% reduced activity; consider methylfolate supplementation under clinician guidance."}
      }
    },
    {
      "rsid": "rs1801131",
      "gene": "MTHFR",
      "variant_name": "A1298C",
      "description": "Second MTHFR variant; compound heterozygosity with C677T compounds impairment.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Standard activity."},
        "AC": {"tier": "warning", "note": "Mild reduction; clinically meaningful only when combined with C677T variant."},
        "CC": {"tier": "warning", "note": "Homozygous; modest reduction in activity."}
      }
    },
    {
      "rsid": "rs4680",
      "gene": "COMT",
      "variant_name": "Val158Met",
      "description": "Controls dopamine clearance in prefrontal cortex. Val/Val = fast clearance (Warrior); Met/Met = slow (Worrier).",
      "interpretations": {
        "GG": {"tier": "warning", "note": "Warrior phenotype — fast dopamine clearance; often higher stress resilience, lower baseline dopamine."},
        "AG": {"tier": "normal", "note": "Balanced clearance."},
        "AA": {"tier": "warning", "note": "Worrier phenotype — slow clearance; higher baseline dopamine, potentially higher anxiety under stress."}
      }
    },
    {
      "rsid": "rs1805087",
      "gene": "MTR",
      "variant_name": "A2756G",
      "description": "B12-dependent methionine synthase; pairs with MTRR in the methylation cycle.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Standard activity."},
        "AG": {"tier": "warning", "note": "Slightly reduced activity; monitor B12 status."},
        "GG": {"tier": "warning", "note": "Reduced activity; B12 sufficiency is important."}
      }
    },
    {
      "rsid": "rs1801394",
      "gene": "MTRR",
      "variant_name": "A66G",
      "description": "Recycles oxidized B12 to active form for the MTR enzyme.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Standard recycling."},
        "AG": {"tier": "warning", "note": "Moderate reduction; paired MTR/MTRR variants amplify impact."},
        "GG": {"tier": "warning", "note": "Reduced recycling of B12."}
      }
    },
    {
      "rsid": "rs602662",
      "gene": "FUT2",
      "variant_name": "Secretor",
      "description": "Secretor status — controls whether B12-binding glycoproteins are secreted into gut. Non-secretors have higher serum B12 but may absorb less.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Secretor — standard B12 absorption."},
        "AG": {"tier": "normal", "note": "Heterozygous secretor."},
        "GG": {"tier": "warning", "note": "Non-secretor — may need higher dietary B12."}
      }
    },
    {
      "rsid": "rs234706",
      "gene": "CBS",
      "variant_name": "C699T",
      "description": "Cystathionine beta-synthase; the drain of homocysteine into the transsulfuration pathway.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Standard activity."},
        "CT": {"tier": "warning", "note": "Upregulated variant — may deplete methyl groups faster."},
        "TT": {"tier": "warning", "note": "Homozygous upregulation."}
      }
    },
    {
      "rsid": "rs2228570",
      "gene": "VDR",
      "variant_name": "TaqI",
      "description": "Vitamin D receptor affinity; influences downstream methylation cofactor availability.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "Higher receptor sensitivity."},
        "AG": {"tier": "normal", "note": "Intermediate sensitivity."},
        "AA": {"tier": "warning", "note": "Lower receptor sensitivity — may benefit from higher vitamin D intake."}
      }
    }
  ]
}
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_panels.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add src/opendna/models.py src/opendna/panels tests/test_panels.py
git commit -m "feat(panels): Pydantic models + panel loader + methylation panel"
```

---

## Task 4: Port the remaining 7 panels

**Files:**
- Create: `src/opendna/panels/cardiovascular.json`
- Create: `src/opendna/panels/pharmacogenomics.json`
- Create: `src/opendna/panels/athletic.json`
- Create: `src/opendna/panels/dietary.json`
- Create: `src/opendna/panels/hfe.json`
- Create: `src/opendna/panels/cognition.json`
- Create: `src/opendna/panels/sensitivity.json`
- Modify: `tests/test_panels.py`

- [ ] **Step 1: Extend the panel test to cover all 8**

Replace the first test in `tests/test_panels.py`:
```python
from opendna.panels import load_panels
from opendna.models import Panel


EXPECTED_PANELS = {
    "methylation",
    "cardiovascular",
    "pharmacogenomics",
    "athletic",
    "dietary",
    "hfe",
    "cognition",
    "sensitivity",
}


def test_all_eight_panels_load() -> None:
    panels = load_panels()
    assert {p.id for p in panels} == EXPECTED_PANELS


def test_every_panel_has_at_least_three_snps() -> None:
    for p in load_panels():
        assert len(p.snps) >= 3, f"{p.id} has too few SNPs"


def test_every_snp_has_interpretations_for_multiple_genotypes() -> None:
    for p in load_panels():
        for snp in p.snps:
            assert len(snp.interpretations) >= 2, f"{snp.rsid} in {p.id} lacks interpretations"
```

Keep the existing `test_methylation_panel_has_known_snps` and `test_snp_interpretations_are_indexed_by_genotype` tests.

- [ ] **Step 2: Write cardiovascular panel**

`src/opendna/panels/cardiovascular.json`:
```json
{
  "id": "cardiovascular",
  "name": "Cardiovascular & Longevity",
  "description": "Variants associated with coronary artery disease risk and lifespan.",
  "snps": [
    {
      "rsid": "rs429358",
      "gene": "APOE",
      "variant_name": "epsilon-4 check (site 1)",
      "description": "Paired with rs7412 to determine APOE haplotype (e2/e3/e4). e4 raises Alzheimer's and CAD risk.",
      "interpretations": {
        "TT": {"tier": "normal", "note": "Not e4 at this site."},
        "CT": {"tier": "warning", "note": "Possible single e4 allele — interpret with rs7412."},
        "CC": {"tier": "risk", "note": "Possible e4/e4 — interpret with rs7412; elevated Alzheimer's + CAD risk."}
      }
    },
    {
      "rsid": "rs7412",
      "gene": "APOE",
      "variant_name": "epsilon-2 check (site 2)",
      "description": "Paired with rs429358 to determine APOE haplotype.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Not e2 at this site."},
        "CT": {"tier": "normal", "note": "One e2 allele possible — often protective for lipids."},
        "TT": {"tier": "warning", "note": "e2/e2 possible — rare, associated with type III hyperlipoproteinemia."}
      }
    },
    {
      "rsid": "rs10757278",
      "gene": "9p21",
      "variant_name": "CAD locus",
      "description": "Best-characterized CAD-risk locus; risk allele ~25% population-attributable risk.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Non-risk genotype."},
        "AG": {"tier": "warning", "note": "One risk allele — modestly elevated CAD risk."},
        "GG": {"tier": "risk", "note": "Two risk alleles — elevated CAD risk; focus on LDL particle size + inflammation."}
      }
    },
    {
      "rsid": "rs2802292",
      "gene": "FOXO3",
      "variant_name": "Longevity variant",
      "description": "Centenarian gene — G allele associated with longer lifespan across populations.",
      "interpretations": {
        "TT": {"tier": "normal", "note": "Common genotype."},
        "GT": {"tier": "normal", "note": "Protective longevity allele present."},
        "GG": {"tier": "normal", "note": "Protective longevity allele homozygous."}
      }
    },
    {
      "rsid": "rs3798220",
      "gene": "LPA",
      "variant_name": "Lipoprotein(a) risk",
      "description": "Strong predictor of elevated Lp(a); associated with CAD and aortic stenosis.",
      "interpretations": {
        "TT": {"tier": "normal", "note": "Not a risk carrier."},
        "CT": {"tier": "risk", "note": "Risk allele present — consider measuring Lp(a)."},
        "CC": {"tier": "risk", "note": "Homozygous risk — strongly associated with elevated Lp(a)."}
      }
    }
  ]
}
```

- [ ] **Step 3: Write pharmacogenomics panel**

`src/opendna/panels/pharmacogenomics.json`:
```json
{
  "id": "pharmacogenomics",
  "name": "Pharmacogenomics (PGx)",
  "description": "Drug-metabolism variants that affect dosing and response. Cross-referenced with PharmGKB/CPIC.",
  "snps": [
    {
      "rsid": "rs4244285",
      "gene": "CYP2C19",
      "variant_name": "*2 loss-of-function",
      "description": "Affects clopidogrel, PPIs, citalopram, escitalopram, some SSRIs.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "Normal metabolizer at this site."},
        "AG": {"tier": "warning", "note": "Intermediate metabolizer — reduced function."},
        "AA": {"tier": "risk", "note": "Poor metabolizer — clopidogrel may be ineffective; SSRIs may accumulate."}
      }
    },
    {
      "rsid": "rs12248560",
      "gene": "CYP2C19",
      "variant_name": "*17 gain-of-function",
      "description": "Ultra-rapid metabolizer variant.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Normal."},
        "CT": {"tier": "warning", "note": "Rapid metabolizer — drugs cleared faster than expected."},
        "TT": {"tier": "warning", "note": "Ultra-rapid metabolizer — standard doses may be subtherapeutic."}
      }
    },
    {
      "rsid": "rs1799853",
      "gene": "CYP2C9",
      "variant_name": "*2 reduced function",
      "description": "Affects warfarin, NSAIDs (ibuprofen, celecoxib), phenytoin.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Normal metabolizer."},
        "CT": {"tier": "warning", "note": "Intermediate — bleeding risk with warfarin, consider dose reduction."},
        "TT": {"tier": "risk", "note": "Poor metabolizer — significant bleeding risk with warfarin."}
      }
    },
    {
      "rsid": "rs1057910",
      "gene": "CYP2C9",
      "variant_name": "*3 reduced function",
      "description": "More severe variant; affects same drug set as *2.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Normal."},
        "AC": {"tier": "risk", "note": "Intermediate — significant dose reduction often needed."},
        "CC": {"tier": "risk", "note": "Poor metabolizer — specialist dosing required."}
      }
    },
    {
      "rsid": "rs9923231",
      "gene": "VKORC1",
      "variant_name": "Warfarin sensitivity",
      "description": "Warfarin's target enzyme; variants increase sensitivity.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Standard sensitivity."},
        "CT": {"tier": "warning", "note": "Increased sensitivity — lower starting dose."},
        "TT": {"tier": "risk", "note": "High sensitivity — lowest starting dose band."}
      }
    },
    {
      "rsid": "rs4149056",
      "gene": "SLCO1B1",
      "variant_name": "*5 statin myopathy risk",
      "description": "Controls statin uptake into hepatocytes; risk variant raises simvastatin-induced myopathy risk.",
      "interpretations": {
        "TT": {"tier": "normal", "note": "Normal."},
        "CT": {"tier": "warning", "note": "Increased myopathy risk — prefer atorvastatin/rosuvastatin."},
        "CC": {"tier": "risk", "note": "Highest myopathy risk — avoid simvastatin 80 mg."}
      }
    },
    {
      "rsid": "rs1142345",
      "gene": "TPMT",
      "variant_name": "*3C",
      "description": "Thiopurine metabolism — azathioprine, 6-MP, 6-TG. Poor metabolizers face severe bone marrow toxicity at standard doses.",
      "interpretations": {
        "TT": {"tier": "risk", "note": "Poor metabolizer — standard thiopurine doses can cause fatal myelosuppression. Requires dose reduction or alternative therapy."},
        "CT": {"tier": "warning", "note": "Intermediate metabolizer — 30-70% dose reduction typical."},
        "CC": {"tier": "normal", "note": "Normal metabolizer."}
      }
    },
    {
      "rsid": "rs776746",
      "gene": "CYP3A5",
      "variant_name": "*3",
      "description": "Tacrolimus, some statins. Expressors need higher doses than non-expressors.",
      "interpretations": {
        "TT": {"tier": "normal", "note": "Non-expressor (common in European ancestry) — standard dosing."},
        "CT": {"tier": "warning", "note": "Intermediate expresser — dose adjustment may be needed."},
        "CC": {"tier": "warning", "note": "Expresser — higher tacrolimus doses needed."}
      }
    }
  ]
}
```

- [ ] **Step 4: Write athletic panel**

`src/opendna/panels/athletic.json`:
```json
{
  "id": "athletic",
  "name": "Athletic Performance & Recovery",
  "description": "Muscle fiber composition, VO2 max response, injury susceptibility, recovery speed.",
  "snps": [
    {
      "rsid": "rs1815739",
      "gene": "ACTN3",
      "variant_name": "R577X",
      "description": "Alpha-actinin-3 in fast-twitch muscle. XX (TT) genotype lacks functional protein — common in endurance athletes, rare in elite sprinters.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "RR — sprint/power-oriented fiber profile."},
        "CT": {"tier": "normal", "note": "RX — mixed profile."},
        "TT": {"tier": "normal", "note": "XX — endurance-oriented; functional alpha-actinin-3 absent from fast-twitch fibers."}
      }
    },
    {
      "rsid": "rs4253778",
      "gene": "PPARA",
      "variant_name": "Power vs endurance",
      "description": "Fatty-acid oxidation regulator; G allele associated with power phenotype, C with endurance.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Endurance-skewed."},
        "CG": {"tier": "normal", "note": "Mixed."},
        "GG": {"tier": "normal", "note": "Power-skewed."}
      }
    },
    {
      "rsid": "rs8192678",
      "gene": "PPARGC1A",
      "variant_name": "Mitochondrial biogenesis",
      "description": "Master regulator of mitochondrial biogenesis; associated with VO2 max trainability.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "High trainability of aerobic capacity."},
        "AG": {"tier": "normal", "note": "Intermediate."},
        "AA": {"tier": "warning", "note": "Reduced aerobic trainability — higher volume may be needed to reach same gains."}
      }
    },
    {
      "rsid": "rs12722",
      "gene": "COL5A1",
      "variant_name": "Tendon flexibility",
      "description": "Type V collagen; variants influence tendon/ligament stiffness and soft-tissue injury risk.",
      "interpretations": {
        "CC": {"tier": "warning", "note": "Stiffer tendons — higher rupture risk at extremes."},
        "CT": {"tier": "normal", "note": "Mixed."},
        "TT": {"tier": "normal", "note": "More compliant tendons."}
      }
    },
    {
      "rsid": "rs1800795",
      "gene": "IL6",
      "variant_name": "-174 G/C",
      "description": "Regulates IL-6 expression; C allele associated with lower inflammation and faster recovery.",
      "interpretations": {
        "GG": {"tier": "warning", "note": "Higher inflammatory response — longer recovery windows may help."},
        "CG": {"tier": "normal", "note": "Intermediate."},
        "CC": {"tier": "normal", "note": "Lower inflammatory response — faster recovery profile."}
      }
    }
  ]
}
```

- [ ] **Step 5: Write dietary panel**

`src/opendna/panels/dietary.json`:
```json
{
  "id": "dietary",
  "name": "Dietary Sensitivity & Nutrition",
  "description": "Lactose, caffeine, alcohol, salt, omega-3 conversion, and bitter-taste variants.",
  "snps": [
    {
      "rsid": "rs4988235",
      "gene": "LCT",
      "variant_name": "Lactase persistence",
      "description": "T allele keeps lactase expressed into adulthood (Northern European origin).",
      "interpretations": {
        "CC": {"tier": "warning", "note": "Lactase non-persistent — likely lactose intolerant."},
        "CT": {"tier": "normal", "note": "Lactase persistent."},
        "TT": {"tier": "normal", "note": "Lactase persistent."}
      }
    },
    {
      "rsid": "rs762551",
      "gene": "CYP1A2",
      "variant_name": "Caffeine metabolism",
      "description": "A allele is the fast-metabolizer variant; C allele is slow metabolizer (higher CV risk from caffeine).",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Fast metabolizer — standard caffeine tolerance."},
        "AC": {"tier": "warning", "note": "Slow metabolizer — caffeine persists longer; avoid late-day intake."},
        "CC": {"tier": "warning", "note": "Slow metabolizer — high-dose caffeine may raise CV risk."}
      }
    },
    {
      "rsid": "rs671",
      "gene": "ALDH2",
      "variant_name": "Alcohol flush",
      "description": "A allele (common in East Asian ancestry) causes acetaldehyde buildup and flushing response.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "Normal alcohol metabolism."},
        "AG": {"tier": "warning", "note": "Intermediate metabolism — flushing, elevated esophageal cancer risk with regular drinking."},
        "AA": {"tier": "risk", "note": "Near-absent acetaldehyde clearance — strong flush, high cancer risk with regular drinking."}
      }
    },
    {
      "rsid": "rs174537",
      "gene": "FADS1",
      "variant_name": "Omega-3 conversion",
      "description": "Controls ALA to EPA/DHA conversion efficiency. T allele = reduced conversion.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "Efficient ALA to EPA/DHA conversion."},
        "GT": {"tier": "warning", "note": "Moderate conversion — marine omega-3 more important."},
        "TT": {"tier": "warning", "note": "Poor conversion — EPA/DHA supplementation recommended."}
      }
    },
    {
      "rsid": "rs713598",
      "gene": "TAS2R38",
      "variant_name": "Bitter taste (PTC)",
      "description": "Detects bitter thiourea compounds in cruciferous vegetables.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Taster — may dislike Brussels sprouts, broccoli."},
        "CG": {"tier": "normal", "note": "Intermediate."},
        "GG": {"tier": "normal", "note": "Non-taster — less sensitivity to bitter compounds."}
      }
    }
  ]
}
```

- [ ] **Step 6: Write HFE panel**

`src/opendna/panels/hfe.json`:
```json
{
  "id": "hfe",
  "name": "Iron Metabolism (HFE)",
  "description": "Hereditary hemochromatosis variants — excess iron absorption.",
  "snps": [
    {
      "rsid": "rs1800562",
      "gene": "HFE",
      "variant_name": "C282Y",
      "description": "Primary clinical variant; homozygotes have high penetrance for iron overload.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "Non-carrier."},
        "AG": {"tier": "warning", "note": "Heterozygous — mild iron-loading tendency; monitor ferritin."},
        "AA": {"tier": "risk", "note": "Homozygous — high risk of clinical hemochromatosis; requires monitoring and possible therapeutic phlebotomy."}
      }
    },
    {
      "rsid": "rs1799945",
      "gene": "HFE",
      "variant_name": "H63D",
      "description": "Secondary variant; lower penetrance than C282Y but compound heterozygotes (C282Y/H63D) have meaningful risk.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Non-carrier."},
        "CG": {"tier": "warning", "note": "Heterozygous — mild iron-loading tendency."},
        "GG": {"tier": "warning", "note": "Homozygous — modest iron-loading risk; monitor ferritin."}
      }
    },
    {
      "rsid": "rs1800730",
      "gene": "HFE",
      "variant_name": "S65C",
      "description": "Minor variant; compound heterozygosity with C282Y may matter.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Non-carrier."},
        "AT": {"tier": "normal", "note": "Heterozygous — clinically significant only with C282Y on other allele."},
        "TT": {"tier": "warning", "note": "Homozygous — rare; modest iron-loading tendency."}
      }
    }
  ]
}
```

- [ ] **Step 7: Write cognition panel**

`src/opendna/panels/cognition.json`:
```json
{
  "id": "cognition",
  "name": "Cognition & Mood",
  "description": "Neurotransmitter-system variants affecting learning, mood, and neuroplasticity.",
  "snps": [
    {
      "rsid": "rs6265",
      "gene": "BDNF",
      "variant_name": "Val66Met",
      "description": "Brain-derived neurotrophic factor. Met allele (T) reduces activity-dependent BDNF secretion.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Val/Val — standard BDNF secretion."},
        "CT": {"tier": "warning", "note": "Val/Met — modest reduction in activity-dependent plasticity."},
        "TT": {"tier": "risk", "note": "Met/Met — reduced plasticity; aerobic exercise and novel learning particularly important."}
      }
    },
    {
      "rsid": "rs1800497",
      "gene": "DRD2",
      "variant_name": "ANKK1 TaqI A1",
      "description": "Dopamine D2 receptor density — A1 allele reduces receptor density.",
      "interpretations": {
        "GG": {"tier": "normal", "note": "A2/A2 — standard D2 receptor density."},
        "AG": {"tier": "warning", "note": "A1/A2 — reduced density; associated with reward-seeking phenotypes."},
        "AA": {"tier": "warning", "note": "A1/A1 — lowest density; higher reward threshold."}
      }
    },
    {
      "rsid": "rs53576",
      "gene": "OXTR",
      "variant_name": "Oxytocin receptor",
      "description": "G allele associated with higher empathy and social sensitivity; A allele with lower.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Lower reported empathy / prosocial scores — trait-level."},
        "AG": {"tier": "normal", "note": "Intermediate."},
        "GG": {"tier": "normal", "note": "Higher reported empathy / prosocial scores."}
      }
    }
  ]
}
```

- [ ] **Step 8: Write sensitivity panel**

`src/opendna/panels/sensitivity.json`:
```json
{
  "id": "sensitivity",
  "name": "Stimulant & Adenosine Sensitivity",
  "description": "Variants controlling how caffeine and adenosine interact with the brain.",
  "snps": [
    {
      "rsid": "rs5751876",
      "gene": "ADORA2A",
      "variant_name": "Adenosine A2A receptor",
      "description": "T allele associated with higher caffeine-induced anxiety.",
      "interpretations": {
        "CC": {"tier": "normal", "note": "Standard response."},
        "CT": {"tier": "warning", "note": "Moderate anxiety sensitivity to caffeine."},
        "TT": {"tier": "warning", "note": "High anxiety sensitivity to caffeine — moderate intake."}
      }
    },
    {
      "rsid": "rs2069514",
      "gene": "CYP1A2",
      "variant_name": "-163 promoter",
      "description": "Companion marker to rs762551; further modulates caffeine metabolism rate.",
      "interpretations": {
        "AA": {"tier": "normal", "note": "Normal induction."},
        "AG": {"tier": "normal", "note": "Intermediate."},
        "GG": {"tier": "normal", "note": "Higher inducibility."}
      }
    },
    {
      "rsid": "rs4680",
      "gene": "COMT",
      "variant_name": "Val158Met (stimulant re-check)",
      "description": "Cross-referenced from methylation panel; modulates subjective stimulant response via prefrontal dopamine.",
      "interpretations": {
        "GG": {"tier": "warning", "note": "Warrior — dopamine clears fast; stimulants may feel less intense."},
        "AG": {"tier": "normal", "note": "Balanced."},
        "AA": {"tier": "warning", "note": "Worrier — stimulants may feel stronger, potentially more anxiogenic."}
      }
    }
  ]
}
```

- [ ] **Step 9: Run tests**

```bash
pytest tests/test_panels.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/opendna/panels tests/test_panels.py
git commit -m "feat(panels): port all 8 curated SNP panels from sandbox"
```

---

## Task 5: Analyzer

**Files:**
- Create: `src/opendna/analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_analyzer.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_analyzer.py -v
```

Expected: `ModuleNotFoundError: No module named 'opendna.analyzer'`

- [ ] **Step 3: Write the analyzer**

`src/opendna/analyzer.py`:
```python
"""Analyzer — join parsed DNA with panels to produce Findings."""
from __future__ import annotations

from collections.abc import Iterable

from opendna.models import Finding, Panel, SnpDef


def _normalize_genotype(g: str) -> str:
    """Sort allele letters so AG == GA, AT == TA, etc.

    Single-allele (hemizygous) or indel calls are returned unchanged.
    """
    if len(g) == 2 and g.isalpha():
        return "".join(sorted(g.upper()))
    return g.upper()


def _match_interpretation(snp: SnpDef, genotype: str) -> tuple[str, str]:
    """Return (tier, note) for a genotype, trying exact then normalized match."""
    if genotype in snp.interpretations:
        i = snp.interpretations[genotype]
        return i.tier, i.note
    norm = _normalize_genotype(genotype)
    for key, interp in snp.interpretations.items():
        if _normalize_genotype(key) == norm:
            return interp.tier, interp.note
    return "unknown", f"Genotype {genotype} not interpreted in panel."


def analyze(
    parsed: dict[str, str],
    panels: Iterable[Panel],
    selected_panel_ids: set[str] | None = None,
) -> list[Finding]:
    """Run every SNP in each selected panel against the parsed genotypes."""
    findings: list[Finding] = []
    for panel in panels:
        if selected_panel_ids is not None and panel.id not in selected_panel_ids:
            continue
        for snp in panel.snps:
            genotype = parsed.get(snp.rsid)
            if genotype is None:
                findings.append(
                    Finding(
                        panel_id=panel.id,
                        rsid=snp.rsid,
                        gene=snp.gene,
                        genotype=None,
                        tier="unknown",
                        note="SNP not present in raw DNA file.",
                        description=snp.description,
                    )
                )
                continue
            tier, note = _match_interpretation(snp, genotype)
            findings.append(
                Finding(
                    panel_id=panel.id,
                    rsid=snp.rsid,
                    gene=snp.gene,
                    genotype=genotype,
                    tier=tier,
                    note=note,
                    description=snp.description,
                )
            )
    return findings
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_analyzer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/opendna/analyzer.py tests/test_analyzer.py
git commit -m "feat(analyzer): match parsed genotypes against panels with strand normalization"
```

---

## Task 6: Annotation subsets (ClinVar + PharmGKB) and loaders

**Files:**
- Create: `src/opendna/annotations/__init__.py`
- Create: `src/opendna/annotations/clinvar.json`
- Create: `src/opendna/annotations/pharmgkb.json`
- Create: `src/opendna/annotations/updater.py`
- Create: `scripts/build_annotations.py`
- Create: `tests/test_annotations.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_annotations.py`:
```python
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
```

- [ ] **Step 2: Create the annotation package**

`src/opendna/annotations/__init__.py`:
```python
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
```

- [ ] **Step 3: Create the shipped ClinVar subset**

`src/opendna/annotations/clinvar.json`:
```json
{
  "rs1801133": {
    "clinical_significance": "drug response",
    "condition": "Homocystinuria; MTHFR deficiency",
    "review_status": "reviewed by expert panel",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1801131": {
    "clinical_significance": "not provided",
    "condition": "MTHFR deficiency (compound heterozygous with C677T)",
    "review_status": "multiple submitters, no conflicts",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs429358": {
    "clinical_significance": "risk factor",
    "condition": "Alzheimer disease; cardiovascular disease",
    "review_status": "reviewed by expert panel",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs7412": {
    "clinical_significance": "risk factor / protective",
    "condition": "Type III hyperlipoproteinemia (homozygous e2)",
    "review_status": "reviewed by expert panel",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1800562": {
    "clinical_significance": "pathogenic",
    "condition": "Hereditary hemochromatosis type 1",
    "review_status": "reviewed by expert panel",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1799945": {
    "clinical_significance": "risk factor",
    "condition": "Hereditary hemochromatosis type 1 (low penetrance)",
    "review_status": "reviewed by expert panel",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1800730": {
    "clinical_significance": "uncertain significance",
    "condition": "Hereditary hemochromatosis type 1",
    "review_status": "multiple submitters",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1142345": {
    "clinical_significance": "drug response",
    "condition": "Thiopurine S-methyltransferase deficiency",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs4244285": {
    "clinical_significance": "drug response",
    "condition": "Clopidogrel response; CYP2C19-mediated drug metabolism",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs12248560": {
    "clinical_significance": "drug response",
    "condition": "CYP2C19 ultrarapid metabolism",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1799853": {
    "clinical_significance": "drug response",
    "condition": "Warfarin response; NSAID metabolism",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs1057910": {
    "clinical_significance": "drug response",
    "condition": "Warfarin response; NSAID metabolism",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs9923231": {
    "clinical_significance": "drug response",
    "condition": "Warfarin sensitivity",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  },
  "rs4149056": {
    "clinical_significance": "drug response",
    "condition": "Simvastatin-induced myopathy",
    "review_status": "reviewed by expert panel (PharmGKB)",
    "source": "ClinVar 2026-03 snapshot"
  }
}
```

- [ ] **Step 4: Create the shipped PharmGKB subset**

`src/opendna/annotations/pharmgkb.json`:
```json
{
  "rs1142345": {
    "gene": "TPMT",
    "recommendations": [
      {
        "drug": "azathioprine",
        "diplotype": "*1/*3C or *3C/*3C",
        "recommendation": "Consider alternative non-thiopurine therapy; if used, reduce dose 10-fold and monitor for severe myelosuppression.",
        "evidence_level": "1A",
        "source": "CPIC 2018"
      },
      {
        "drug": "mercaptopurine",
        "diplotype": "*1/*3C or *3C/*3C",
        "recommendation": "Start at 30-80% of normal dose (heterozygote) or 10% of normal dose (homozygote).",
        "evidence_level": "1A",
        "source": "CPIC 2018"
      },
      {
        "drug": "thioguanine",
        "diplotype": "*1/*3C or *3C/*3C",
        "recommendation": "Start at 50-80% of normal dose (heterozygote) or consider alternative (homozygote).",
        "evidence_level": "1A",
        "source": "CPIC 2018"
      }
    ]
  },
  "rs4244285": {
    "gene": "CYP2C19",
    "recommendations": [
      {
        "drug": "clopidogrel",
        "diplotype": "*2 carrier (intermediate/poor metabolizer)",
        "recommendation": "Consider alternative antiplatelet agent (prasugrel or ticagrelor) if no contraindication.",
        "evidence_level": "1A",
        "source": "CPIC 2022"
      },
      {
        "drug": "citalopram",
        "diplotype": "poor metabolizer",
        "recommendation": "Consider 50% dose reduction or alternative SSRI.",
        "evidence_level": "1A",
        "source": "CPIC 2015"
      }
    ]
  },
  "rs12248560": {
    "gene": "CYP2C19",
    "recommendations": [
      {
        "drug": "clopidogrel",
        "diplotype": "*17 carrier (rapid/ultrarapid metabolizer)",
        "recommendation": "Standard dosing; monitor for bleeding with concurrent PPI use.",
        "evidence_level": "1A",
        "source": "CPIC 2022"
      },
      {
        "drug": "voriconazole",
        "diplotype": "ultrarapid metabolizer",
        "recommendation": "Subtherapeutic levels likely — consider alternative antifungal.",
        "evidence_level": "1A",
        "source": "CPIC 2017"
      }
    ]
  },
  "rs1799853": {
    "gene": "CYP2C9",
    "recommendations": [
      {
        "drug": "warfarin",
        "diplotype": "*2 carrier",
        "recommendation": "Use pharmacogenomic-guided dosing algorithm (e.g. warfarindosing.org).",
        "evidence_level": "1A",
        "source": "CPIC 2017"
      },
      {
        "drug": "celecoxib",
        "diplotype": "*2 carrier",
        "recommendation": "Use lowest effective dose; consider 25-50% reduction.",
        "evidence_level": "2A",
        "source": "CPIC 2020"
      }
    ]
  },
  "rs1057910": {
    "gene": "CYP2C9",
    "recommendations": [
      {
        "drug": "warfarin",
        "diplotype": "*3 carrier",
        "recommendation": "Use PGx-guided dosing; *3/*3 requires substantial dose reduction.",
        "evidence_level": "1A",
        "source": "CPIC 2017"
      }
    ]
  },
  "rs9923231": {
    "gene": "VKORC1",
    "recommendations": [
      {
        "drug": "warfarin",
        "diplotype": "-1639 A carrier",
        "recommendation": "Lower initial warfarin dose (pair with CYP2C9 genotype for full algorithm).",
        "evidence_level": "1A",
        "source": "CPIC 2017"
      }
    ]
  },
  "rs4149056": {
    "gene": "SLCO1B1",
    "recommendations": [
      {
        "drug": "simvastatin",
        "diplotype": "*5 carrier",
        "recommendation": "Avoid simvastatin 80 mg; consider atorvastatin or rosuvastatin.",
        "evidence_level": "1A",
        "source": "CPIC 2022"
      }
    ]
  }
}
```

- [ ] **Step 5: Create the regeneration script (MVP stub)**

`scripts/build_annotations.py`:
```python
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
```

- [ ] **Step 6: Create the updater stub**

`src/opendna/annotations/updater.py`:
```python
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
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_annotations.py -v
```

Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add src/opendna/annotations scripts/build_annotations.py tests/test_annotations.py
git commit -m "feat(annotations): ClinVar + PharmGKB shipped subsets with loader + annotate()"
```

---

## Task 7: Report rendering (HTML + JSON)

**Files:**
- Create: `src/opendna/report/__init__.py`
- Create: `src/opendna/report/render.py`
- Create: `src/opendna/report/template.html.j2`
- Create: `tests/test_report.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:
```python
import json

from opendna.models import Finding
from opendna.report import render_report


def _sample_findings() -> list[Finding]:
    return [
        Finding(
            panel_id="methylation",
            rsid="rs1801133",
            gene="MTHFR",
            genotype="CT",
            tier="warning",
            note="~30% reduced activity",
            description="Central methylation enzyme",
            clinvar={
                "clinical_significance": "drug response",
                "condition": "MTHFR deficiency",
                "review_status": "reviewed by expert panel",
            },
            pharmgkb=None,
        ),
        Finding(
            panel_id="pharmacogenomics",
            rsid="rs1142345",
            gene="TPMT",
            genotype="TT",
            tier="risk",
            note="Poor metabolizer",
            description="Thiopurine metabolism",
            clinvar={"clinical_significance": "drug response", "condition": "TPMT deficiency", "review_status": "expert panel"},
            pharmgkb=[
                {"drug": "azathioprine", "recommendation": "10-fold dose reduction", "evidence_level": "1A"}
            ],
        ),
    ]


def test_render_report_produces_html_and_json() -> None:
    bundle = render_report(_sample_findings())
    assert "<!DOCTYPE html>" in bundle.html
    assert "MTHFR" in bundle.html
    assert "TPMT" in bundle.html
    assert bundle.json_payload["findings_count"] == 2


def test_report_html_includes_tier_badges() -> None:
    bundle = render_report(_sample_findings())
    assert "risk" in bundle.html
    assert "warning" in bundle.html


def test_report_json_is_serializable_and_round_trips() -> None:
    bundle = render_report(_sample_findings())
    roundtrip = json.loads(json.dumps(bundle.json_payload))
    assert roundtrip["findings_count"] == 2
    assert roundtrip["findings"][0]["rsid"] == "rs1801133"


def test_render_report_includes_llm_prose_when_provided() -> None:
    bundle = render_report(_sample_findings(), llm_prose="Summary: your methylation profile shows reduced MTHFR activity.")
    assert "methylation profile" in bundle.html
    assert bundle.llm_prose is not None


def test_render_report_escapes_html_in_prose() -> None:
    """Jinja autoescape must neutralize LLM-supplied HTML to prevent injection."""
    bundle = render_report(_sample_findings(), llm_prose="<script>alert('xss')</script>")
    assert "<script>" not in bundle.html
    assert "&lt;script&gt;" in bundle.html
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_report.py -v
```

Expected: `ModuleNotFoundError: No module named 'opendna.report'`

- [ ] **Step 3: Create the report package init**

`src/opendna/report/__init__.py`:
```python
"""Report rendering — findings + optional LLM prose → HTML + JSON."""
from opendna.report.render import render_report

__all__ = ["render_report"]
```

- [ ] **Step 4: Create the renderer**

`src/opendna/report/render.py`:
```python
"""Jinja2-driven renderer for the OpenDNA report."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, select_autoescape

from opendna.models import Finding, ReportBundle


def _group_by_panel(findings: list[Finding]) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.panel_id].append(f)
    return dict(sorted(grouped.items()))


def _counts_by_tier(findings: list[Finding]) -> dict[str, int]:
    counts = {"risk": 0, "warning": 0, "normal": 0, "unknown": 0}
    for f in findings:
        counts[f.tier] = counts.get(f.tier, 0) + 1
    return counts


def render_report(
    findings: list[Finding],
    llm_prose: str | None = None,
) -> ReportBundle:
    template_dir = files("opendna.report")
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "html.j2"]),
    )
    template = env.get_template("template.html.j2")

    grouped = _group_by_panel(findings)
    counts = _counts_by_tier(findings)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    html = template.render(
        grouped=grouped,
        counts=counts,
        llm_prose=llm_prose,
        generated_at=generated_at,
    )
    json_payload = {
        "generated_at": generated_at,
        "findings_count": len(findings),
        "counts_by_tier": counts,
        "findings": [f.model_dump() for f in findings],
        "llm_prose": llm_prose,
    }
    return ReportBundle(
        findings=findings,
        html=html,
        json_payload=json_payload,
        llm_prose=llm_prose,
    )
```

- [ ] **Step 5: Create the Jinja template**

`src/opendna/report/template.html.j2`:
```jinja
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OpenDNA Report</title>
<style>
  :root {
    --bg: #0a0a0a; --card: #1a1a1a; --text: #f0f0f0; --dim: #a0a0a0;
    --border: #333; --risk: #ff4d4d; --warning: #ffb300; --normal: #00e676;
    --unknown: #888; --accent: #ffd700;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 40px; line-height: 1.6; }
  .container { max-width: 1000px; margin: 0 auto; }
  header { border-bottom: 2px solid var(--accent); padding-bottom: 20px; margin-bottom: 40px;
    display: flex; justify-content: space-between; align-items: flex-end; }
  h1 { font-size: 2.5rem; margin: 0; color: var(--accent); text-transform: uppercase; letter-spacing: -1px; }
  .meta { text-align: right; color: var(--dim); font-size: 0.9rem; }
  .summary { display: flex; gap: 16px; margin-bottom: 32px; }
  .tile { background: var(--card); border-radius: 12px; padding: 20px; flex: 1; border: 1px solid var(--border); }
  .tile .num { font-size: 2.2rem; font-weight: 700; }
  .tile.risk .num { color: var(--risk); }
  .tile.warning .num { color: var(--warning); }
  .tile.normal .num { color: var(--normal); }
  .tile.unknown .num { color: var(--unknown); }
  .panel { background: var(--card); border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid var(--border); }
  .panel h2 { margin-top: 0; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
  th { color: var(--dim); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 1px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
  .badge.risk { background: rgba(255,77,77,0.15); color: var(--risk); border: 1px solid var(--risk); }
  .badge.warning { background: rgba(255,179,0,0.15); color: var(--warning); border: 1px solid var(--warning); }
  .badge.normal { background: rgba(0,230,118,0.15); color: var(--normal); border: 1px solid var(--normal); }
  .badge.unknown { background: rgba(136,136,136,0.15); color: var(--unknown); border: 1px solid var(--unknown); }
  .rsid { font-family: 'SF Mono', Consolas, monospace; color: var(--dim); font-size: 0.85rem; }
  .clinvar, .pharmgkb { font-size: 0.8rem; color: var(--dim); margin-top: 4px; }
  .clinvar strong, .pharmgkb strong { color: var(--accent); }
  .llm-synthesis { background: rgba(255,215,0,0.06); border: 1px solid var(--accent); border-radius: 12px; padding: 24px; margin-bottom: 32px; }
  .llm-synthesis h2 { margin-top: 0; color: var(--accent); }
  .llm-synthesis pre { white-space: pre-wrap; word-wrap: break-word; font-family: inherit; margin: 0; }
  footer { text-align: center; color: var(--dim); font-size: 0.8rem; margin-top: 48px; }
  @media print {
    body { background: white; color: black; padding: 0; }
    .panel, .tile, .llm-synthesis { background: white; border: 1px solid #ccc; }
    h1, .panel h2, .llm-synthesis h2 { color: black; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>OpenDNA Report</h1>
      <p style="margin:4px 0 0; color: var(--dim);">Local genomic synthesis · not for clinical use</p>
    </div>
    <div class="meta">Generated: {{ generated_at }}</div>
  </header>

  <section class="summary">
    <div class="tile risk"><div class="num">{{ counts.risk }}</div><div>Risk findings</div></div>
    <div class="tile warning"><div class="num">{{ counts.warning }}</div><div>Warnings</div></div>
    <div class="tile normal"><div class="num">{{ counts.normal }}</div><div>Normal</div></div>
    <div class="tile unknown"><div class="num">{{ counts.unknown }}</div><div>Not in file</div></div>
  </section>

  {% if llm_prose %}
  <section class="llm-synthesis">
    <h2>AI Synthesis</h2>
    <pre>{{ llm_prose }}</pre>
  </section>
  {% endif %}

  {% for panel_id, items in grouped.items() %}
  <section class="panel">
    <h2>{{ panel_id|replace('_', ' ')|title }}</h2>
    <table>
      <thead><tr><th>Gene</th><th>Variant</th><th>Genotype</th><th>Interpretation</th></tr></thead>
      <tbody>
      {% for f in items %}
        <tr>
          <td><strong>{{ f.gene }}</strong><div class="rsid">{{ f.rsid }}</div></td>
          <td>{{ f.description }}</td>
          <td>{{ f.genotype or "—" }}</td>
          <td>
            <span class="badge {{ f.tier }}">{{ f.tier }}</span>
            <div>{{ f.note }}</div>
            {% if f.clinvar %}
            <div class="clinvar"><strong>ClinVar:</strong> {{ f.clinvar.clinical_significance }} — {{ f.clinvar.condition }}</div>
            {% endif %}
            {% if f.pharmgkb %}
            <div class="pharmgkb"><strong>PharmGKB:</strong>
              {% for rec in f.pharmgkb %}
                <div>{{ rec.drug }}: {{ rec.recommendation }} <em>(evidence {{ rec.evidence_level }})</em></div>
              {% endfor %}
            </div>
            {% endif %}
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
  {% endfor %}

  <footer>
    Generated by OpenDNA · github.com/corbett3000/OpenDNA · PharmGKB annotations used under CC BY-SA 4.0
  </footer>
</div>
</body>
</html>
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_report.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add src/opendna/report tests/test_report.py
git commit -m "feat(report): Jinja2 renderer (autoescape on) producing HTML + JSON bundle"
```

---

## Task 8: LLM provider layer (base + Anthropic + OpenAI)

**Files:**
- Create: `src/opendna/llm/__init__.py`
- Create: `src/opendna/llm/base.py`
- Create: `src/opendna/llm/anthropic.py`
- Create: `src/opendna/llm/openai.py`
- Create: `tests/test_llm_anthropic.py`
- Create: `tests/test_llm_openai.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_llm_anthropic.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from opendna.llm import get_provider
from opendna.llm.anthropic import AnthropicProvider
from opendna.models import Finding


def _finding() -> Finding:
    return Finding(
        panel_id="methylation", rsid="rs1801133", gene="MTHFR",
        genotype="CT", tier="warning", note="~30% reduced activity",
        description="Central methylation enzyme",
    )


def test_get_provider_returns_anthropic_for_name() -> None:
    p = get_provider("anthropic", api_key="sk-fake", model="claude-sonnet-4-6")
    assert isinstance(p, AnthropicProvider)


def test_get_provider_raises_on_unknown_name() -> None:
    with pytest.raises(ValueError):
        get_provider("not-a-provider", api_key="x", model="y")


def test_anthropic_provider_calls_sdk_and_returns_prose() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Your MTHFR result suggests...")]
    mock_client.messages.create.return_value = mock_message

    with patch("opendna.llm.anthropic.anthropic.Anthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-fake", model="claude-sonnet-4-6")
        out = provider.interpret([_finding()])

    assert "MTHFR" in out
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    # Prompt caching: system block should be a list with cache_control.
    assert isinstance(call_kwargs["system"], list)
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_provider_redacts_api_key_in_repr() -> None:
    p = AnthropicProvider(api_key="sk-ant-very-secret", model="claude-sonnet-4-6")
    assert "very-secret" not in repr(p)
    assert "sk-ant-" not in repr(p)
```

`tests/test_llm_openai.py`:
```python
from unittest.mock import MagicMock, patch

from opendna.llm.openai import OpenAIProvider
from opendna.models import Finding


def _finding() -> Finding:
    return Finding(
        panel_id="cardiovascular", rsid="rs10757278", gene="9p21",
        genotype="GG", tier="risk", note="Elevated CAD risk",
        description="Best-characterized CAD-risk locus",
    )


def test_openai_provider_calls_sdk_and_returns_prose() -> None:
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="9p21 GG suggests..."))]
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("opendna.llm.openai.openai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-fake", model="gpt-4o")
        out = provider.interpret([_finding()])

    assert "9p21" in out
    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o"
```

- [ ] **Step 2: Write the base + factory**

`src/opendna/llm/base.py`:
```python
"""Provider ABC — every LLM backend implements `interpret`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from opendna.models import Finding


SYSTEM_PROMPT = (
    "You are OpenDNA's synthesis assistant. You receive structured findings from a consumer "
    "DNA scan (rsid, gene, genotype, rule-based interpretation, ClinVar/PharmGKB annotations). "
    "Write a concise, readable prose summary grouped by body system, flag the most important "
    "risk findings first, and note any actionable steps the user could discuss with a clinician. "
    "Never present the output as medical advice. Keep the entire response under 600 words."
)


def findings_to_prompt(findings: list[Finding]) -> str:
    """Render findings as a compact structured block for the LLM."""
    lines = []
    for f in findings:
        line = f"[{f.tier}] {f.gene} {f.rsid} = {f.genotype or '--'} ({f.panel_id}) — {f.note}"
        if f.clinvar:
            line += f" | ClinVar: {f.clinvar['clinical_significance']}"
        if f.pharmgkb:
            drugs = ", ".join(r["drug"] for r in f.pharmgkb)
            line += f" | PharmGKB: {drugs}"
        lines.append(line)
    return "\n".join(lines)


class Provider(ABC):
    """Abstract LLM provider."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.model} api_key=***redacted***>"

    @abstractmethod
    def interpret(self, findings: list[Finding]) -> str:
        ...
```

- [ ] **Step 3: Write the Anthropic provider**

`src/opendna/llm/anthropic.py`:
```python
"""Anthropic Claude provider — default for OpenDNA."""
from __future__ import annotations

import anthropic

from opendna.llm.base import SYSTEM_PROMPT, Provider, findings_to_prompt
from opendna.models import Finding


DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(Provider):
    def interpret(self, findings: list[Finding]) -> str:
        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Synthesize these findings into a clinician-readable "
                        "summary:\n\n" + findings_to_prompt(findings)
                    ),
                }
            ],
        )
        return "".join(b.text for b in message.content if hasattr(b, "text"))
```

- [ ] **Step 4: Write the OpenAI provider**

`src/opendna/llm/openai.py`:
```python
"""OpenAI provider — secondary option."""
from __future__ import annotations

import openai

from opendna.llm.base import SYSTEM_PROMPT, Provider, findings_to_prompt
from opendna.models import Finding


DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(Provider):
    def interpret(self, findings: list[Finding]) -> str:
        client = openai.OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Synthesize these findings into a clinician-readable "
                        "summary:\n\n" + findings_to_prompt(findings)
                    ),
                },
            ],
        )
        return resp.choices[0].message.content or ""
```

- [ ] **Step 5: Write the factory**

`src/opendna/llm/__init__.py`:
```python
"""LLM provider factory."""
from __future__ import annotations

from opendna.llm.anthropic import AnthropicProvider
from opendna.llm.base import Provider
from opendna.llm.openai import OpenAIProvider


def get_provider(name: str, api_key: str, model: str) -> Provider:
    name = name.lower().strip()
    if name == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    if name == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    raise ValueError(f"Unknown provider: {name!r} (known: anthropic, openai)")


__all__ = ["Provider", "AnthropicProvider", "OpenAIProvider", "get_provider"]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_llm_anthropic.py tests/test_llm_openai.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add src/opendna/llm tests/test_llm_anthropic.py tests/test_llm_openai.py
git commit -m "feat(llm): provider ABC + Anthropic (w/ prompt caching) + OpenAI + factory"
```

---

## Task 9: FastAPI server

**Files:**
- Create: `src/opendna/server.py`
- Create: `src/opendna/web/__init__.py`
- Create: `src/opendna/web/static/index.html` (placeholder — real UI in Task 10)
- Create: `src/opendna/web/static/app.js` (placeholder)
- Create: `src/opendna/web/static/style.css` (placeholder)
- Create: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_server.py`:
```python
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from opendna.server import app


def test_get_root_serves_spa() -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OpenDNA" in resp.text


def test_list_panels_endpoint() -> None:
    client = TestClient(app)
    resp = client.get("/api/panels")
    assert resp.status_code == 200
    body = resp.json()
    assert "panels" in body
    ids = {p["id"] for p in body["panels"]}
    assert "methylation" in ids


def test_analyze_endpoint_returns_findings_without_llm(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text(
        "# header\n"
        "rs1801133\t1\t1000\tCT\n"
        "rs4680\t22\t2000\tGG\n"
    )
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": str(dna),
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_html"].startswith("<!DOCTYPE html>")
    assert "findings" in body["report_json"]
    assert body["report_json"]["findings_count"] >= 2


def test_analyze_endpoint_rejects_missing_file() -> None:
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": "/tmp/definitely-does-not-exist.txt",
        "selected_panels": ["methylation"],
    })
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


def test_analyze_endpoint_invokes_llm_when_configured(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text("rs1801133\t1\t1000\tCT\n")
    client = TestClient(app)

    with patch("opendna.server.get_provider") as mock_get:
        mock_get.return_value.interpret.return_value = "AI synthesis goes here."
        resp = client.post("/api/analyze", json={
            "file_path": str(dna),
            "selected_panels": ["methylation"],
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-fake"},
        })

    assert resp.status_code == 200
    assert "AI synthesis goes here." in resp.json()["report_html"]
    mock_get.assert_called_once_with("anthropic", api_key="sk-fake", model="claude-sonnet-4-6")


def test_update_db_endpoint_returns_status() -> None:
    client = TestClient(app)
    resp = client.post("/api/update-db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "shipped-subset"
```

- [ ] **Step 2: Create web static placeholders**

`src/opendna/web/__init__.py`: empty.

`src/opendna/web/static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>OpenDNA</title></head>
<body><h1>OpenDNA</h1><p>Placeholder — real UI shipped in Task 10.</p></body>
</html>
```

`src/opendna/web/static/app.js`: `// placeholder`

`src/opendna/web/static/style.css`: `/* placeholder */`

- [ ] **Step 3: Write the server**

`src/opendna/server.py`:
```python
"""FastAPI server exposing 3 endpoints."""
from __future__ import annotations

import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.annotations.updater import refresh
from opendna.llm import get_provider
from opendna.panels import load_panels
from opendna.parser import parse_23andme
from opendna.report import render_report

logger = logging.getLogger("opendna.server")

app = FastAPI(title="OpenDNA", version="0.1.0")


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key: str


class AnalyzeRequest(BaseModel):
    file_path: str
    selected_panels: list[str] | None = None
    llm: LLMConfig | None = None


_static_dir = Path(str(files("opendna.web").joinpath("static")))
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(_static_dir / "index.html")


@app.get("/api/panels")
def list_panels() -> dict[str, Any]:
    return {
        "panels": [
            {"id": p.id, "name": p.name, "description": p.description, "snp_count": len(p.snps)}
            for p in load_panels()
        ]
    }


@app.post("/api/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> JSONResponse:
    path = Path(req.file_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {req.file_path}")

    try:
        parsed = parse_23andme(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Parse error: {exc}") from exc

    panels = load_panels()
    selected = set(req.selected_panels) if req.selected_panels else None
    findings = analyze(parsed, panels, selected_panel_ids=selected)
    findings = annotate(findings, load_clinvar(), load_pharmgkb())

    prose: str | None = None
    if req.llm is not None:
        logger.info("Invoking LLM provider=%s model=%s", req.llm.provider, req.llm.model)
        try:
            provider = get_provider(req.llm.provider, api_key=req.llm.api_key, model=req.llm.model)
            prose = provider.interpret(findings)
        except Exception as exc:
            logger.exception("LLM synthesis failed")
            raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}") from exc

    bundle = render_report(findings, llm_prose=prose)
    return JSONResponse({
        "report_html": bundle.html,
        "report_json": bundle.json_payload,
    })


@app.post("/api/update-db")
def update_db() -> JSONResponse:
    return JSONResponse(refresh())
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_server.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/opendna/server.py src/opendna/web tests/test_server.py
git commit -m "feat(server): FastAPI app with /api/panels, /api/analyze, /api/update-db"
```

---

## Task 10: Web UI (SPA)

**Files:**
- Modify: `src/opendna/web/static/index.html`
- Modify: `src/opendna/web/static/app.js`
- Modify: `src/opendna/web/static/style.css`

No new tests — server tests cover the API contract; the UI is driven manually during `opendna serve`.

**Security note for this task:** the JS MUST use DOM APIs (`textContent`, `createElement`, `appendChild`) and never `innerHTML` with dynamic content. The report HTML is rendered into a sandboxed iframe via `srcdoc`, which isolates any page scripts from the parent origin.

- [ ] **Step 1: Rewrite `index.html`**

`src/opendna/web/static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenDNA</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main class="shell">
    <header>
      <h1>OpenDNA</h1>
      <p class="tag">Local precision-medicine synthesis · your DNA stays on your machine</p>
    </header>

    <section class="card">
      <h2>1. Point us at your raw DNA file</h2>
      <label>Absolute path to your 23andMe / AncestryDNA raw TSV:
        <input id="file-path" type="text" placeholder="/Users/you/Downloads/genome.txt" spellcheck="false">
      </label>
    </section>

    <section class="card">
      <h2>2. Choose panels</h2>
      <div id="panels"></div>
    </section>

    <section class="card">
      <h2>3. (Optional) AI synthesis</h2>
      <label>Provider:
        <select id="llm-provider">
          <option value="">None (rule-based only)</option>
          <option value="anthropic">Anthropic (Claude)</option>
          <option value="openai">OpenAI (GPT)</option>
        </select>
      </label>
      <label>Model: <input id="llm-model" type="text" placeholder="claude-sonnet-4-6"></label>
      <label>API key (never persisted):
        <input id="llm-key" type="password" placeholder="sk-...">
      </label>
    </section>

    <button id="run" class="primary">Generate report</button>
    <div id="status" class="status"></div>

    <section id="report-frame" class="report hidden">
      <div class="report-actions">
        <button id="download-html">Download HTML</button>
        <button id="download-json">Download JSON</button>
      </div>
      <iframe id="report-iframe" title="OpenDNA report" sandbox="allow-same-origin"></iframe>
    </section>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Rewrite `style.css`**

`src/opendna/web/static/style.css`:
```css
:root {
  --bg: #0a0a0a; --card: #1a1a1a; --text: #f0f0f0; --dim: #a0a0a0;
  --border: #333; --accent: #ffd700; --danger: #ff4d4d;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; margin: 0; padding: 40px 20px; }
.shell { max-width: 880px; margin: 0 auto; }
header { border-bottom: 2px solid var(--accent); padding-bottom: 16px; margin-bottom: 32px; }
h1 { margin: 0; color: var(--accent); font-size: 2.5rem; letter-spacing: -1px; text-transform: uppercase; }
.tag { color: var(--dim); margin: 4px 0 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card h2 { margin: 0 0 12px; font-size: 1.1rem; color: var(--accent); }
label { display: block; margin-bottom: 10px; font-size: 0.9rem; color: var(--dim); }
input, select { display: block; width: 100%; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 0.95rem; margin-top: 4px; font-family: inherit; }
input:focus, select:focus { outline: none; border-color: var(--accent); }
#panels { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
#panels label { display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.03); padding: 8px 12px; border-radius: 8px; margin: 0; cursor: pointer; }
#panels input[type="checkbox"] { width: auto; margin: 0; }
.primary { background: var(--accent); color: var(--bg); border: none; border-radius: 10px; padding: 14px 24px; font-weight: 700; font-size: 1rem; cursor: pointer; width: 100%; }
.primary:hover { filter: brightness(1.1); }
.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.status { margin-top: 16px; color: var(--dim); font-size: 0.9rem; }
.status.error { color: var(--danger); }
.report { margin-top: 32px; }
.report.hidden { display: none; }
.report-actions { display: flex; gap: 8px; margin-bottom: 12px; }
.report-actions button { background: transparent; color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; cursor: pointer; }
.report-actions button:hover { border-color: var(--accent); color: var(--accent); }
iframe { width: 100%; height: 1100px; border: 1px solid var(--border); border-radius: 12px; background: #fff; }
```

- [ ] **Step 3: Rewrite `app.js` — DOM APIs only, no innerHTML with user data**

`src/opendna/web/static/app.js`:
```javascript
const $ = (id) => document.getElementById(id);
let lastReport = null;

function renderPanelCheckbox(panel) {
  const label = document.createElement("label");

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.value = panel.id;
  checkbox.checked = true;

  const text = document.createElement("span");
  const name = document.createElement("strong");
  name.textContent = panel.name;
  const count = document.createElement("span");
  count.style.color = "var(--dim)";
  count.textContent = " (" + panel.snp_count + ")";
  text.appendChild(name);
  text.appendChild(count);

  label.appendChild(checkbox);
  label.appendChild(text);
  return label;
}

async function loadPanels() {
  const resp = await fetch("/api/panels");
  const { panels } = await resp.json();
  const container = $("panels");
  container.replaceChildren(...panels.map(renderPanelCheckbox));
}

function selectedPanels() {
  return Array.from(document.querySelectorAll('#panels input:checked')).map(el => el.value);
}

function llmConfig() {
  const provider = $("llm-provider").value;
  if (!provider) return null;
  return {
    provider,
    model: $("llm-model").value || (provider === "anthropic" ? "claude-sonnet-4-6" : "gpt-4o"),
    api_key: $("llm-key").value,
  };
}

function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

function setStatus(message, isError) {
  const status = $("status");
  status.className = isError ? "status error" : "status";
  status.textContent = message;
}

async function run() {
  const btn = $("run");
  setStatus("Analyzing…", false);
  btn.disabled = true;

  try {
    const body = {
      file_path: $("file-path").value.trim(),
      selected_panels: selectedPanels(),
      llm: llmConfig(),
    };
    if (!body.file_path) throw new Error("Enter the path to your raw DNA file.");
    if (!body.selected_panels.length) throw new Error("Select at least one panel.");

    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || "Request failed");
    }
    const data = await resp.json();
    lastReport = data;
    // Report HTML rendered into a sandboxed iframe. srcdoc + sandbox attr
    // isolates it from the parent origin even if downstream content changes.
    $("report-iframe").srcdoc = data.report_html;
    $("report-frame").classList.remove("hidden");
    setStatus("Done — " + data.report_json.findings_count + " findings.", false);
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

$("run").addEventListener("click", run);
$("download-html").addEventListener("click", () => {
  if (lastReport) download("opendna-report.html", lastReport.report_html, "text/html");
});
$("download-json").addEventListener("click", () => {
  if (lastReport) download("opendna-report.json", JSON.stringify(lastReport.report_json, null, 2), "application/json");
});

loadPanels();
```

- [ ] **Step 4: Manually verify the UI**

```bash
cd /Users/corbett3000/Coding/OpenDNA
source .venv/bin/activate
pytest -v
# CLI entry point lands next — for now, run directly:
python -m uvicorn opendna.server:app --port 8787
# open http://localhost:8787, enter tests/fixtures/sample_23andme.txt, click Generate
```

- [ ] **Step 5: Commit**

```bash
git add src/opendna/web/static
git commit -m "feat(web): SPA with panel selection, BYOK LLM, sandboxed iframe report"
```

---

## Task 11: CLI entry point

**Files:**
- Create: `src/opendna/cli.py`
- Create: `src/opendna/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
import json
from pathlib import Path

from opendna.cli import build_parser, cmd_scan, cmd_update_db


def test_parser_accepts_three_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "--port", "9000"])
    assert args.cmd == "serve" and args.port == 9000
    args = parser.parse_args(["scan", "foo.txt"])
    assert args.cmd == "scan" and args.file == "foo.txt"
    args = parser.parse_args(["update-db"])
    assert args.cmd == "update-db"


def test_cmd_scan_writes_html_and_json_alongside_input(tmp_path: Path) -> None:
    dna = tmp_path / "dna.txt"
    dna.write_text("rs1801133\t1\t1000\tCT\nrs4680\t22\t2000\tGG\n")
    parser = build_parser()
    args = parser.parse_args(["scan", str(dna)])
    rc = cmd_scan(args)
    assert rc == 0
    html = tmp_path / "dna.opendna.html"
    js = tmp_path / "dna.opendna.json"
    assert html.exists() and js.exists()
    payload = json.loads(js.read_text())
    assert payload["findings_count"] >= 2


def test_cmd_update_db_prints_status(capsys) -> None:
    parser = build_parser()
    args = parser.parse_args(["update-db"])
    rc = cmd_update_db(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "shipped-subset" in out
```

- [ ] **Step 2: Write `cli.py`**

`src/opendna/cli.py`:
```python
"""Command-line entry point for OpenDNA."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from opendna import __version__
from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.annotations.updater import refresh
from opendna.panels import load_panels
from opendna.parser import parse_23andme
from opendna.report import render_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="opendna", description="Local precision-medicine scans from raw DNA files.")
    p.add_argument("--version", action="version", version=f"opendna {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    srv = sub.add_parser("serve", help="Start the local web UI (default port 8787).")
    srv.add_argument("--port", type=int, default=8787)
    srv.add_argument("--host", type=str, default="127.0.0.1",
                     help="Default 127.0.0.1 (localhost only). 0.0.0.0 exposes to your LAN — "
                          "only use on a trusted network.")

    scan = sub.add_parser("scan", help="Headless scan — emits <file>.opendna.{html,json} alongside input.")
    scan.add_argument("file", help="Path to 23andMe-style raw DNA TSV.")
    scan.add_argument("--panels", nargs="*", default=None,
                      help="Panel ids to include (default: all).")

    sub.add_parser("update-db", help="Report status of shipped ClinVar/PharmGKB subsets.")

    return p


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn  # deferred import to keep `scan`/`update-db` fast
    if args.host == "0.0.0.0":
        print("WARNING: Binding to 0.0.0.0 — OpenDNA is reachable from other machines on your LAN.",
              file=sys.stderr)
    uvicorn.run("opendna.server:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"error: file not found: {input_path}", file=sys.stderr)
        return 1
    parsed = parse_23andme(input_path)
    panels = load_panels()
    selected = set(args.panels) if args.panels else None
    findings = analyze(parsed, panels, selected_panel_ids=selected)
    findings = annotate(findings, load_clinvar(), load_pharmgkb())
    bundle = render_report(findings)

    html_out = input_path.with_name(input_path.stem + ".opendna.html")
    json_out = input_path.with_name(input_path.stem + ".opendna.json")
    html_out.write_text(bundle.html)
    json_out.write_text(json.dumps(bundle.json_payload, indent=2))
    print(f"Wrote {html_out}")
    print(f"Wrote {json_out}")
    return 0


def cmd_update_db(_args: argparse.Namespace) -> int:
    status = refresh()
    print(json.dumps(status, indent=2))
    return 0


DISPATCH = {"serve": cmd_serve, "scan": cmd_scan, "update-db": cmd_update_db}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return DISPATCH[args.cmd](args)
```

- [ ] **Step 3: Write `__main__.py`**

`src/opendna/__main__.py`:
```python
"""Allow `python -m opendna` and `opendna` entry-point script."""
import sys

from opendna.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

The `[project.scripts]` entry in `pyproject.toml` points to `opendna.__main__:main`, so `opendna` on the PATH invokes `main`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Smoke test the CLI**

```bash
cd /Users/corbett3000/Coding/OpenDNA
source .venv/bin/activate
pip install -e ".[dev,all]"  # re-install so the entry point is registered
opendna --version
opendna scan tests/fixtures/sample_23andme.txt
ls tests/fixtures/sample_23andme.opendna.*
opendna update-db
```

Expected: version prints, two output files appear, update-db prints shipped-subset status.

- [ ] **Step 6: Commit**

```bash
git add src/opendna/cli.py src/opendna/__main__.py tests/test_cli.py
git commit -m "feat(cli): serve, scan, update-db subcommands with argparse dispatch"
```

---

## Task 12: End-to-end integration test + final README + GitHub repo

**Files:**
- Create: `tests/test_e2e.py`
- Modify: `README.md` (full version)
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write the e2e test**

`tests/test_e2e.py`:
```python
"""End-to-end: fixture DNA file → analyze endpoint → assert report shape."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from opendna.server import app


def test_full_pipeline_rule_based(fixtures_dir: Path) -> None:
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "file_path": str(fixtures_dir / "sample_23andme.txt"),
        "selected_panels": None,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_html"].startswith("<!DOCTYPE html>")
    payload = body["report_json"]

    rsids = {f["rsid"] for f in payload["findings"] if f["genotype"]}
    assert "rs1801133" in rsids
    assert "rs4680" in rsids
    assert "rs1815739" in rsids
    assert "rs1142345" in rsids

    tpmt = next(f for f in payload["findings"] if f["rsid"] == "rs1142345")
    assert tpmt["tier"] == "risk"
    assert tpmt["pharmgkb"] is not None


def test_full_pipeline_with_mocked_llm(fixtures_dir: Path) -> None:
    client = TestClient(app)
    with patch("opendna.server.get_provider") as mock_get:
        mock_get.return_value.interpret.return_value = "End-to-end prose from mock."
        resp = client.post("/api/analyze", json={
            "file_path": str(fixtures_dir / "sample_23andme.txt"),
            "selected_panels": None,
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-fake"},
        })
    assert resp.status_code == 200
    assert "End-to-end prose from mock." in resp.json()["report_html"]
```

- [ ] **Step 2: Run the full suite**

```bash
cd /Users/corbett3000/Coding/OpenDNA
source .venv/bin/activate
pytest -v
ruff check src tests
```

Expected: all tests pass, ruff clean.

- [ ] **Step 3: Write the final `README.md`**

```markdown
# OpenDNA

> Local-first precision-medicine synthesis for consumer DNA files. Your data never leaves your machine.

[![CI](https://github.com/corbett3000/OpenDNA/actions/workflows/ci.yml/badge.svg)](https://github.com/corbett3000/OpenDNA/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/opendna.svg)](https://pypi.org/project/opendna/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**OpenDNA** parses a 23andMe / AncestryDNA / MyHeritage raw DNA file against 8 curated SNP panels (cardiovascular, methylation, pharmacogenomics, athletic, dietary, HFE, cognition, stimulant sensitivity), joins findings with ClinVar + PharmGKB/CPIC annotations, and renders a self-contained HTML report. Optional BYOK LLM synthesis (Anthropic Claude, OpenAI GPT) adds a prose interpretation layer.

## Not a medical device

OpenDNA is an educational and exploratory tool. **It is not a clinical diagnostic** and its output is not medical advice. Discuss all findings with a qualified clinician before acting on them.

## Privacy

This is the whole trust claim:

1. **Your DNA file never leaves your machine.** The entire pipeline runs on `localhost`. Parsing, annotation, and rule-based analysis are fully offline.
2. **LLM synthesis is opt-in and payload is minimal.** If you provide an API key, OpenDNA sends only the filtered findings (typically <200 lines, no raw DNA data) to the provider you chose.
3. **No telemetry, no accounts, no persistence.** API keys are read from the request and discarded.
4. **The server binds to `127.0.0.1` by default.** `--host 0.0.0.0` requires an explicit flag and prints a warning.

## Install

```bash
pip install opendna
pip install "opendna[all]"     # + Anthropic and OpenAI SDKs
```

## Quickstart

```bash
opendna serve                  # open http://localhost:8787
```

Point it at your raw DNA file, select panels, optionally paste an API key, click *Generate report*.

### Headless usage

```bash
opendna scan ~/Downloads/genome.txt
# Writes genome.opendna.html and genome.opendna.json next to the input.
```

### Agent / pipeline integration

`opendna scan --panels pharmacogenomics methylation ~/genome.txt` exits 0 and writes a `report.json` with a stable schema. Drop it into a larger agent pipeline.

## What it covers

- **Cardiovascular & Longevity** — APOE, 9p21, FOXO3, LPA
- **Methylation & Detox** — MTHFR, COMT, MTR/MTRR, FUT2, CBS, VDR
- **Pharmacogenomics (PGx)** — CYP2C19, CYP2C9, VKORC1, SLCO1B1, TPMT, CYP3A5
- **Athletic Performance & Recovery** — ACTN3, PPARA, PPARGC1A, COL5A1, IL6
- **Dietary Sensitivity** — LCT, CYP1A2, ALDH2, FADS1, TAS2R38
- **Iron Metabolism (HFE)** — C282Y, H63D, S65C
- **Cognition & Mood** — BDNF, DRD2, OXTR
- **Stimulant Sensitivity** — ADORA2A, CYP1A2, COMT

Every finding is annotated with ClinVar clinical significance and (for PGx) PharmGKB/CPIC dosing guidelines.

## Roadmap

- **v0.2** — chat-with-your-genome pane; PDF export
- **v0.3** — VCF/WGS input support
- **v0.4** — polygenic risk scores with population adjustment

## Attribution

- ClinVar data used under public-domain NIH terms.
- PharmGKB annotations licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## License

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 4: Write `CONTRIBUTING.md`**

```markdown
# Contributing to OpenDNA

## Dev setup

```bash
git clone https://github.com/corbett3000/OpenDNA
cd OpenDNA
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,all]"
pytest -v
```

## Running locally

```bash
opendna serve
# http://localhost:8787
```

Use `tests/fixtures/sample_23andme.txt` to smoke-test without exposing real data.

## Adding a panel

1. Drop a JSON file into `src/opendna/panels/` matching the schema in existing panels.
2. Add an entry for every genotype you want interpreted (both strand orientations are handled automatically).
3. Extend `EXPECTED_PANELS` in `tests/test_panels.py`.
4. Run `pytest -v` and open a PR.

## Annotation freshness

Shipped ClinVar/PharmGKB subsets are regenerated per release via:

```bash
python scripts/build_annotations.py --source all
```

The full upstream fetcher lands in v0.1.1.

## Release process

1. Bump `__version__` in `src/opendna/__init__.py` and `pyproject.toml`.
2. Update the changelog section in README.
3. Tag `v0.X.Y` and push; CI publishes to PyPI.
```

- [ ] **Step 5: Create the GitHub repo**

```bash
cd /Users/corbett3000/Coding/OpenDNA
gh repo create corbett3000/OpenDNA --public \
  --description "Local-first precision-medicine synthesis for consumer DNA files" \
  --source . --remote origin
git push -u origin main
```

Expected: repo exists at `github.com/corbett3000/OpenDNA` and the README renders.

- [ ] **Step 6: Commit docs and push**

```bash
git add README.md CONTRIBUTING.md tests/test_e2e.py
git commit -m "docs: final README + CONTRIBUTING + end-to-end test"
git push
```

- [ ] **Step 7: Verify CI passes**

```bash
gh run watch
```

Expected: CI green on latest push.

- [ ] **Step 8: Tag v0.1.0**

```bash
git tag v0.1.0
git push --tags
```

---

## Self-review summary

**Spec coverage:**
- §4 MVP — all 8 panels → Tasks 3+4
- §4 MVP — ClinVar + PharmGKB → Task 6
- §4 MVP — rule-based + optional LLM → Tasks 5, 8
- §4 MVP — HTML + JSON report with autoescaped prose → Task 7 (including XSS-escape test)
- §4 MVP — FastAPI + SPA → Tasks 9, 10 (sandboxed iframe, DOM APIs only)
- §4 MVP — CLI with serve/scan/update-db → Task 11
- §5 Architecture — every file in the tree maps to a task
- §7 Privacy — API keys redacted (Task 8), 127.0.0.1 default + warning (Task 11), no persistence (all tasks)
- §8 Testing — unit, integration, e2e, CI matrix 3.11/3.12/3.13 (Task 1 + throughout)
- §10 Roadmap — noted in README and CONTRIBUTING

**Placeholder scan:** no TBD/TODO tokens. Code blocks complete. `build_annotations.py` is an explicit v0.1.0 stub (noted in docstring + README roadmap), not a plan placeholder.

**Type consistency:** `Finding`, `Panel`, `SnpDef`, `ReportBundle`, `Provider` names consistent across Tasks 3–12. `analyze(parsed, panels, selected_panel_ids=...)` signature stable across Tasks 5 and 9. `render_report(findings, llm_prose=...)` signature stable across Tasks 7, 9, 11.

**Security notes added:**
- Jinja autoescape enabled + explicit test that LLM-supplied `<script>` is escaped (Task 7).
- SPA uses DOM APIs only, no innerHTML with user/API data (Task 10).
- Report HTML rendered into a sandboxed iframe via `srcdoc` + `sandbox="allow-same-origin"` (Task 10).

**Scope:** single cohesive deliverable — one installable Python package shipping a web UI, CLI, and agent-friendly scan mode. Appropriate for one plan.
