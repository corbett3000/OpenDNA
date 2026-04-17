# OpenDNA — Claude Code Orientation

Terse primer. See [README.md](README.md) for user-facing docs and [docs/superpowers/handover-2026-04-17.md](docs/superpowers/handover-2026-04-17.md) for project history.

## What this is

Local-first web utility that parses a raw 23andMe-style DNA file, matches against 8 curated SNP panels, joins findings with ClinVar + PharmGKB/CPIC annotations, and renders a self-contained HTML report. Optional BYOK LLM synthesis (Anthropic default with prompt caching, OpenAI secondary). Everything runs on `localhost:8787`.

**Repo:** https://github.com/corbett3000/OpenDNA (public, Apache 2.0)

## Quick start in a session

```bash
source .venv/bin/activate            # venv already exists
pytest -v                            # 44 tests, should all pass
opendna serve                        # http://localhost:8787
```

If the venv doesn't exist: `python3 -m venv .venv && pip install -e ".[dev,all]"`.

## Stack

Python 3.11+, FastAPI + Uvicorn, Jinja2 (autoescape on), Pydantic v2, vanilla JS SPA (no build step), Anthropic + OpenAI SDKs, pytest + ruff.

## Layout (at a glance)

```
src/opendna/
├── parser.py                   # 23andMe TSV → dict
├── models.py                   # Pydantic models (Panel, SnpDef, Finding, ReportBundle)
├── panels/*.json               # 8 curated SNP panels
├── annotations/                # ClinVar + PharmGKB shipped subsets + loader
├── analyzer.py                 # panels × DNA × annotations → Findings (with strand + RC normalization)
├── llm/                        # Provider ABC + Anthropic + OpenAI + factory
├── report/                     # Jinja2 renderer + template.html.j2
├── server.py                   # FastAPI app (/, /api/panels, /api/analyze, /api/analyze-stream, /api/update-db)
├── web/static/                 # SPA (index.html, app.js, style.css) — DOM APIs only
├── cli.py                      # argparse subcommands (serve, scan, update-db)
└── __main__.py
```

Tests mirror the layout in `tests/`. Example report at `examples/sample-report.html`; screenshot at `docs/assets/sample-report.png`.

## Load-bearing invariants — DO NOT break these

1. **Raw DNA file never leaves the machine.** The parser is local-only. No code path should transmit the raw file.
2. **LLM calls send only filtered findings**, never raw DNA. If you add a new LLM path, funnel it through `llm/base.py::findings_to_prompt` or an equivalent.
3. **API keys never persisted server-side.** Passed in request body, held in memory for one call, discarded. Redacted in logs + `__repr__`.
4. **Server binds to 127.0.0.1 by default.** `--host 0.0.0.0` requires an explicit flag + visible warning.
5. **Browser localStorage** holds form values only when the user ticks *Remember*. That's the only client-side persistence.
6. **HTML template** uses Jinja autoescape and renders LLM prose inside `<pre>` with no `| safe` filter — XSS test at `tests/test_report.py::test_render_report_escapes_html_in_prose` pins this.
7. **SPA uses DOM APIs, not `innerHTML` with dynamic content.** Report HTML is rendered into a sandboxed iframe via `srcdoc`.

## Before committing / pushing

- `pytest -v` → all passing.
- `ruff check src tests` → clean.
- No `Co-Authored-By: Claude` trailers in commit messages (user preference).
- History was squashed to a single "Initial public release" commit on 2026-04-17. Force-push to main requires explicit user consent — don't just do it.

## Open threads

See [docs/superpowers/handover-2026-04-17.md](docs/superpowers/handover-2026-04-17.md) for the live list. Short version as of 2026-04-17:

- v0.1.1: live-upstream ClinVar + PharmGKB fetcher (currently stubbed in `scripts/build_annotations.py`).
- v0.2: chat-with-your-genome pane; PDF export.
- v0.3: VCF / WGS input parser (different scale — 5M+ variants).
- Final whole-project code review not yet run.
- Not yet published to PyPI.

## User preferences (sticky)

- Prefers tight, direct responses. No trailing summaries of obvious work.
- No Claude co-author in commits.
- Privacy claims must match reality — don't overclaim in docs.
- When a major change lands, restart the local server so the user's browser reflects it (`lsof -ti:8787 | xargs kill; opendna serve --port 8787`).
