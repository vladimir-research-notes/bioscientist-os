# Data

This directory holds **small, committed fixtures** only. No large datasets, no
bulk database dumps, no caches, no secrets are committed here.

```
data/
  fixtures/
    papers/        # small paper metadata + abstract records
    uniprot/       # UniProt-style protein records
    opentargets/   # disease/gene/protein link records
  cache/           # (gitignored) local connector cache, created at runtime
```

## Fixtures

Fixtures are created in Milestone 1 and are deliberately tiny (≈15–30 papers plus
a handful of protein and link records) and **theme-focused** (cellular
senescence / longevity / autophagy). See `fixtures/README.md` for the labeling
convention.

## Labeling: real-style vs. synthetic

Every fixture record carries a `synthetic` flag:

- `synthetic: false` — modeled on a real public record (IDs/metadata may be
  shaped like the real source). We do **not** redistribute bulk content.
- `synthetic: true` — fabricated for illustration where licensing/provenance is
  uncertain. Synthetic records must never be presented as real curated data.

## Cache

`data/cache/` is created at runtime by the cached connector layer (Milestone 6)
and is **gitignored**. It is reproducible and must not be committed.
