# Results

## TL;DR

This document holds **measured** results (counts, metrics, figures) produced by
the milestones. It is intentionally near-empty in the scaffold commit: there are
no functional results to report yet. Each milestone that produces measurable
output appends to this file with exact commands and denominators.

> Do not cite any number here until the corresponding milestone has landed and
> the table below is populated. Empty cells mean *not yet measured*, not zero.

## Build / test status

The only measured results so far concern the build itself, not the pipeline:

| Milestone | Status | Offline test suite |
|-----------|--------|--------------------|
| 0 — package skeleton and runnable CLI | Done | (subsumed) |
| 1 — data schemas and small fixtures | Done | (subsumed) |
| 2 — ingestion and local storage | Done | `python3 -m pytest -q` → **67 passed** |

The 67 tests are the Milestone-0 contract/import/CLI-smoke checks (20), the
Milestone-1 schema and fixture checks (30), and the Milestone-2 storage and
ingestion checks (17): schema JSON round-trips, the enforced
provenance/epistemic/validation rules, fixture loading (counts, `synthetic`
labeling, `data_source` stamping, loud failure on malformed input), and now
ingestion into SQLite (count checks, idempotent re-ingest, two-build
determinism, exact round-trip, and schema-validation-on-ingest). No search,
extraction, evidence, or evaluation *pipeline* numbers exist yet; those land in
Milestones 3–8.

### Fixtures (Milestone 1)

The committed corpus loads and validates via
`python3 -c "from bioscientist_os.fixtures import load_all; print(load_all().summary())"`:

| Fixture set | Count | `synthetic` | Notes |
|-------------|-------|-------------|-------|
| papers (`data/fixtures/papers/papers.json`) | 18 | `true` (all) | fabricated abstracts; test-prefix DOIs (`10.0000/`) |
| proteins (`data/fixtures/uniprot/proteins.json`) | 10 | `false` (all) | modeled on real UniProt accessions; condensed function text |
| associations (`data/fixtures/opentargets/associations.json`) | 9 | `true` (all) | real gene symbols, **fabricated** scores, synthetic disease ids |
| research questions (`data/fixtures/questions.json`) | 3 | n/a | seeds for evidence tables / memos |

These counts describe the fixture set, not pipeline performance. Theme:
cellular senescence / longevity / autophagy. Papers 006 and 007 deliberately
disagree on whether autophagy promotes or restrains senescence, to give later
support/conflict logic real material.

## Result tables (populated by milestones)

### Ingestion (Milestone 2)

Produced by `python3 scripts/01_ingest_fixtures.py` (or
`biosci ingest data/fixtures --db results/raw/bioscientist.db`), then inspected
with `biosci stats --db results/raw/bioscientist.db`. The database is gitignored
and reproducible from the committed fixtures.

| Quantity | Value |
|----------|-------|
| paper fixtures ingested (`papers`) | 18 |
| uniprot fixtures ingested (`database_records`, source `UniProt`) | 10 |
| opentargets link fixtures ingested (`database_records`, source `OpenTargets`) | 9 |
| research questions ingested | 3 |
| total rows | 40 |
| first ingest writes | 40 inserted, 0 updated |
| idempotent re-ingest writes | 0 inserted, 40 updated (no new rows) |
| two-build content digest (sha256) | identical (`f040627…5123da94`) |

Idempotency is verified by re-ingesting into the same database (counts and
content digest unchanged); deterministic creation is verified by ingesting into
two fresh databases and comparing their content digests. The digest is a SHA-256
over the canonical, primary-key-sorted serialization of every data row, so it is
independent of insertion order and on-disk layout. Every ingested row is
*observed metadata* with `data_source = fixture`; no claims or relations are
produced at ingestion.

### Search (Milestone 3)

| Query | Recall@5 | Denominator |
|-------|----------|-------------|
| _pending_ | | |

### Entity / claim extraction (Milestones 4, 8)

| Metric | Value (95% Wilson CI) | Denominator |
|--------|-----------------------|-------------|
| entity precision | _pending_ | |
| entity recall | _pending_ | |
| claim sanity pass rate | _pending_ | |

### Evidence table / provenance (Milestones 5, 8)

| Metric | Value | Denominator |
|--------|-------|-------------|
| evidence rows generated | _pending_ | |
| provenance coverage | _pending_ | |

### Figures (Milestone 7)

Saved under `results/figures/` (gitignored, regenerable). Regeneration commands
are listed in `docs/REPRODUCIBILITY.md`.

## Exact commands

See `docs/REPRODUCIBILITY.md` for the full end-to-end run that regenerates every
number above.

## Limitations

All results are computed on a tiny, partly-synthetic, theme-focused fixture set.
They illustrate pipeline behavior and provenance discipline, **not** population
performance or biological ground truth.
