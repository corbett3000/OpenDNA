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

## License of contributions

By contributing a PR you agree that your changes are licensed to the project under the same [Apache License 2.0](LICENSE) that covers the rest of OpenDNA. No CLA — the license grant is implied by merging.
