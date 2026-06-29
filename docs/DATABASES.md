# Database connectors

## TL;DR

A clean adapter layer (Milestone 6) with a common interface, a required
**fixture-backed** connector, a local cache, retry/error handling, and a
`data_source` provenance field on every record. Live API connectors (PubMed /
Europe PMC / OpenAlex / UniProt / Open Targets / PDB / AlphaFold) are **optional,
off by default, and never required for tests**.

## Short explanation

```
BaseConnector
  ├── FixtureConnector   (reads data/fixtures/*, data_source="fixture")  [required]
  ├── CachedConnector    (wraps any connector; writes data/cache/, data_source="cache")
  └── LiveConnector      (optional; HTTP; data_source="live")            [opt-in]
```

Every returned `DatabaseRecord` records which source it came from, so a memo or
evidence table can show whether a link is committed, cached, or freshly fetched.

## Longer explanation

### Offline-first behavior

The default and test paths use only `FixtureConnector`. The cache layer makes
repeated runs deterministic and avoids network calls. A `LiveConnector` is a thin,
clearly-marked option for users who opt in; it must degrade gracefully (timeouts,
retries with backoff, explicit error records) and must never be a test dependency.

### Targeted databases (fixture-modeled)

| Source | What it models | Status |
|--------|----------------|--------|
| PubMed / NCBI | paper metadata | fixture (live optional) |
| Europe PMC / OpenAlex | paper metadata | optional |
| UniProt | protein records | fixture (live optional) |
| Open Targets | disease/gene/protein links | fixture |
| PDB / AlphaFold | structure links | optional, link-only |

### Licensing and honesty

Where a source's licensing or schema is uncertain, fixtures are **synthetic** and
marked `synthetic: true`. We do not redistribute bulk database content; fixtures
are small, illustrative, and labeled. See `data/fixtures/README.md`.

## Exact commands

```bash
# After Milestone 6 (illustrative):
biosci db lookup --source uniprot --id <fixture-id> --db results/raw/bioscientist.db
```

## Limitations

- Live connectors are best-effort; only the fixture/cache path carries
  correctness/reproducibility guarantees.
- Fixture coverage is small and theme-focused (senescence/longevity/autophagy).
- No bulk download, no rate-limit-heavy crawling, no credentialed endpoints.
