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
| 1 — data schemas and small fixtures | Done | `python3 -m pytest -q` → **50 passed** |

The 50 tests are the Milestone-0 contract/import/CLI-smoke checks (20) plus
Milestone-1 schema and fixture checks (30): schema JSON round-trips, the
enforced provenance/epistemic/validation rules, and fixture loading
(counts, `synthetic` labeling, `data_source` stamping, and loud failure on
malformed input). No ingestion, search, extraction, evidence, or evaluation
*pipeline* numbers exist yet; those land in Milestones 2–8.

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

| Quantity | Value |
|----------|-------|
| paper fixtures ingested | _pending_ |
| uniprot fixtures ingested | _pending_ |
| opentargets link fixtures ingested | _pending_ |
| duplicate-collapse behavior verified | _pending_ |

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
