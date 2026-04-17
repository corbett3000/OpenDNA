# OpenDNA — Design Spec

**Date:** 2026-04-17
**Status:** Draft (pending user review)
**Author:** Peter Corbett
**Repo:** `OpenDNA` (local: `~/Coding/OpenDNA`, GitHub TBD)

---

## 1. One-liner

Open-source, local-first web utility that scans a 23andMe-style raw DNA file against curated SNP panels and renders an AI-interpreted precision-medicine report. Your DNA file never leaves your machine.

## 2. Why this exists

Consumer-genomics users (23andMe, AncestryDNA, MyHeritage) get a raw DNA text file from their provider but no good, private, local tooling to interpret it. Existing options either (a) require uploading the file to a third-party service, (b) are clinical-grade tools with steep learning curves, or (c) are static reports from a single provider.

OpenDNA closes this gap: one command starts a local web UI, you point it at your raw file, you get a self-contained HTML report. Optional LLM synthesis (BYOK — Anthropic, OpenAI) layers prose interpretation on top of the structured findings. Nothing is persisted server-side, nothing leaves localhost unless the user explicitly enables the LLM layer.

## 3. Target user

- **Primary:** Consumer-genomics user with a raw DNA file, comfortable running a `pip install` and pasting a path into a browser. Wants more than the provider's default report, cares about privacy.
- **Secondary:** Developers building agent pipelines who want a programmable step that turns a raw DNA file into structured health findings (`--json` output is a first-class citizen).
- **Out of scope:** clinicians (this is not a medical device), WGS users (23andMe-scale only in MVP).

## 4. Scope

### MVP (in)

- Local FastAPI server with a single-page vanilla-JS UI
- 23andMe-style TSV parser (`rsid\tchromosome\tposition\tgenotype`)
- 8 curated SNP panels ported from the sandbox:
  - Cardiovascular & longevity
  - Methylation & detox
  - Pharmacogenomics (PGx)
  - Athletic performance & recovery
  - Dietary sensitivity & nutrition
  - HFE / hemochromatosis
  - Cognition & mood
  - Caffeine / adenosine sensitivity
- **ClinVar annotation layer** — every finding carries a clinical-significance tag (`Benign`, `Likely pathogenic`, `Uncertain significance`, etc.)
- **PharmGKB / CPIC integration** for the PGx panel — authoritative dosing guidelines per genotype
- Rule-based report rendering (no key required)
- Optional LLM synthesis (Anthropic default, OpenAI secondary)
- Self-contained single-file HTML report + sibling `report.json`
- CLI entry point: `opendna serve`, `opendna scan <file>`, `opendna update-db`

### Non-goals (explicitly deferred)

- **Chat with your genome** — v2 feature
- **WGS / VCF input format** — different parser, different data scale (5M+ variants), different user. v2.
- **Polygenic risk scores** from GWAS summary stats (e.g. PGC psychiatric GWAS) — needs imputation + weighting + population model. v2.
- **Ancestry / Neanderthal breakdown** — different product entirely, out of scope.
- **Population-specific bias correction** — pairs with PRS. v2.
- **PDF export** — v2. HTML prints fine.
- **Biomarker integration** (blood panels, etc.) — different input, different product.
- **User accounts / server-side persistence** — never.
- **Non-English reports** — v2.

## 5. Architecture

```
OpenDNA/
├── pyproject.toml              # package, entry point `opendna`
├── README.md
├── LICENSE                     # MIT
├── src/opendna/
│   ├── __main__.py             # CLI: serve, scan, update-db
│   ├── server.py               # FastAPI app (one process)
│   ├── parser.py               # 23andMe TSV → {rsid: genotype}
│   ├── panels/*.json           # 8 curated panels
│   ├── annotations/
│   │   ├── clinvar.json        # pre-filtered subset, shipped
│   │   ├── pharmgkb.json       # pre-filtered subset, shipped
│   │   └── updater.py          # refreshes from NIH/PharmGKB on demand
│   ├── analyzer.py             # panels × parsed data × annotations → findings
│   ├── llm/
│   │   ├── base.py             # Provider ABC
│   │   ├── anthropic.py        # default; claude-sonnet-4-6 w/ prompt caching
│   │   └── openai.py
│   ├── report/
│   │   ├── render.py           # findings + prose → HTML + JSON
│   │   └── template.html.j2
│   └── web/static/             # index.html, app.js, style.css
├── scripts/
│   └── build_annotations.py    # regenerates pre-filtered subsets from upstream
├── docs/
│   └── superpowers/specs/      # this spec + future ones
└── tests/
```

### HTTP surface

Three endpoints. That's all.

- `GET /` — serves the SPA
- `POST /api/analyze` — body: `{file_path, selected_panels, llm?: {provider, model, api_key}}` → `{findings, report_html, report_json}`
- `POST /api/update-db` — refreshes ClinVar/PharmGKB caches

### Data flow

1. User runs `opendna serve`. Browser opens at `http://localhost:8787`.
2. User pastes a local path to their raw DNA file, picks panels, optionally pastes an LLM API key.
3. Server: parse → run panels → join ClinVar/PharmGKB → (if key present) call LLM provider for synthesis → render HTML + JSON.
4. SPA shows the rendered report inline and offers `Download HTML` / `Download JSON` buttons.

### Key design decisions

| Decision | Choice | Why |
|---|---|---|
| Language / framework | Python 3.11+, FastAPI | Reuses existing sandbox scripts; FastAPI is batteries-included for JSON APIs. |
| UI | Vanilla JS, no build step | Zero contribution friction; no npm/node required. |
| API key handling | Per-request only, never persisted, redacted in logs | Trust claim — must be verifiable by reading 50 lines of code. |
| Annotation data | Pre-filtered subsets shipped in-repo (option A), `opendna update-db` for fresh (option B) | Instant first-run, explicit refresh path. |
| LLM layer | Optional + pluggable via provider ABC | No key → still get a useful rule-based report. Adding Gemini/Groq later is a small PR. |
| Default LLM provider | Anthropic `claude-sonnet-4-6` with prompt caching | Matches user's existing tooling; caching cuts cost on repeat runs. |
| License | MIT | Standard permissive; maximizes adoption. |
| Port | `8787` | Unused by common dev stacks; easy to remember. |

## 6. Data sources

### ClinVar
- Source: NIH ClinVar VCF (`https://ftp.ncbi.nlm.nih.gov/pub/clinvar/`)
- Update cadence: weekly upstream; we ship a quarterly snapshot
- Fields kept: `rsid`, `clinical_significance`, `condition`, `review_status`
- Subset strategy: only rsids referenced by any of our 8 panels (expect <10 KB JSON)
- Regen script: `scripts/build_annotations.py --source clinvar`

### PharmGKB / CPIC
- Source: PharmGKB API + CPIC guideline annotations (CC BY-SA)
- Fields kept: `gene`, `rsid`, `diplotype`, `drug`, `recommendation`, `evidence_level`
- Scope: just the drugs referenced by our PGx panel (~15 drugs)
- Regen script: `scripts/build_annotations.py --source pharmgkb`

Licensing note: ClinVar is public domain. PharmGKB annotations are CC BY-SA — attribution required in the rendered report and README.

## 7. Privacy model

Hard guarantees (enforced by design, documented in README):

1. **No data upload without explicit action.** DNA file stays on the user's filesystem. The only outbound network call happens when the user provides an LLM API key and clicks "Generate interpretation" — and the payload is the filtered findings (~200 rows), never the raw file.
2. **API keys are never persisted.** Passed via the `/api/analyze` request body, held in the request handler's memory, discarded after response. Logs redact them.
3. **No telemetry.** No analytics, no crash reporting, no phone-home.
4. **Server binds to `127.0.0.1` only** by default. `--host 0.0.0.0` requires an explicit flag and a visible warning.

Readme gets a dedicated "Privacy" section near the top.

## 8. Testing strategy

- **Unit:** parser (sample 23andMe fixture), each panel's scoring logic, annotation join, LLM provider adapters (mocked).
- **Integration:** full `analyze` endpoint with fixture DNA file + mocked LLM provider → snapshot the HTML + JSON.
- **CI:** GitHub Actions running pytest on 3.11, 3.12, 3.13 + ruff + mypy. `scripts/build_annotations.py` runs in a scheduled job to catch upstream schema changes early.
- **Manual / golden:** one end-to-end smoke test with the author's own DNA file, documented in `CONTRIBUTING.md` but not in CI.

## 9. Open questions

*None blocking.* The following are deferred decisions to revisit during implementation:

- Packaging: `pip install opendna` (simple) vs. `pipx` recommendation (better isolation for a CLI). Probably: document both.
- Should we ship a `--dry-run` that just lists which rsids from the panels are present in the user's file without running analysis? Nice-to-have.
- Do we allow the user to bring their own panel (`opendna scan --panel my_panel.json`)? Probably yes, but not blocking.

## 10. Roadmap

- **v0.1 (MVP):** everything in §4.
- **v0.2:** chat with your genome (B from original brainstorm); PDF export.
- **v0.3:** VCF / WGS input support.
- **v0.4:** polygenic risk scores from selected GWAS summary-stat sources; population adjustment.
- **v0.5:** ancestry / population admixture (may spin off into a separate project).
