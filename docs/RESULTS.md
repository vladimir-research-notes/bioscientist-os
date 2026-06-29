# Results

## TL;DR

This document holds **measured** results (counts, metrics, figures) produced by
the milestones. It is intentionally near-empty in the scaffold commit: there are
no functional results to report yet. Each milestone that produces measurable
output appends to this file with exact commands and denominators.

> Do not cite any number here until the corresponding milestone has landed and
> the table below is populated. Empty cells mean *not yet measured*, not zero.

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
