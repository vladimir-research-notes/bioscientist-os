# Human review: Milestone 6 — Database connector layer

## TL;DR
Added an offline-first database-connector layer: a `BaseConnector` interface, the
required fixture connectors (`uniprot` / `opentargets` / `papers`), a gitignored
read-through `CachedConnector`, transient-only retry with deterministic backoff, and an
opt-in `LiveConnector` that is off by default and exercised offline with a mock
transport. Every record carries an explicit `data_source` provenance (fixture / cache /
live), stamped by the connector rather than passed through. New `biosci db`
CLI (`sources` / `list` / `lookup`, with `--cache`). 35 new tests (178 total), all
offline. The layer serves observed metadata only — no claim, relation, or biological
assertion.

## What changed
- `src/bioscientist_os/databases/`: `base.py` (interface, errors, retry, stamping),
  `fixture.py` (`FixtureConnector` + factories), `cache.py` (`CachedConnector`),
  `live.py` (opt-in `LiveConnector` + UniProt example), `registry.py`
  (`ConnectorRegistry`, `load_connectors`, `open_connectors`); re-exported from
  `databases/__init__.py`.
- `src/bioscientist_os/cli.py`: `biosci db` sub-app (`sources`, `list`, `lookup` with
  `--cache` / `--cache-dir` / `--json`); `info` status line and module docstring updated
  to Milestones 0–6.
- `tests/test_connectors.py`: fixture lookup + provenance, registry, cache miss/hit +
  offline-first + canonical round-trip, retry/error handling, the live connector via a
  mock transport, and the CLI.
- Docs + website: this note, the milestone note, the commit note; `DATABASES.md`
  (implemented), `RESULTS.md`, `REPRODUCIBILITY.md`; and `site/` (`databases` → Done, and
  `milestones`/`index`/`architecture`/`results` updated to M6 / 178 tests).

## Commands run
- `python3 -m pytest -q` → 178 passed (offline).
- `ruff check src/bioscientist_os/databases/ src/bioscientist_os/cli.py tests/test_connectors.py` → clean.
- `python3 scripts/01_ingest_fixtures.py --reset`, then `biosci db sources/list/lookup`
  (text + `--json`), and two `biosci db lookup --source uniprot --id P05231 --cache`
  runs to confirm the `fixture` → `cache` provenance transition and the cache file.

## Test status
178 passed, 0 failed, offline. 35 of the tests are new (`tests/test_connectors.py`). No
network is opened and no real sleeping occurs (the transport and `sleep` are injected).

## Known limitations
- Live connectors are **best-effort and never run in CI**; only the fixture/cache path
  carries correctness/reproducibility guarantees. The shipped `uniprot_live_connector`
  is a minimal, defensive example, not a complete UniProt client, and its JSON parse is
  untested against the real API.
- The cache is keyed by `(source, record_id)` and never invalidated/refreshed — a cache
  hit always wins (by design, for offline-first determinism); there is no TTL.
- The `papers` connector's records (`Paper`) have no per-record `source` field, so
  `db lookup --json` shows top-level `"source": null` for papers (the `data_source`
  provenance is still present). This is honest, but could read as missing data.
- Connector coverage is the three fixture sources only; the optional PubMed / Europe PMC
  / OpenAlex / Open Targets / PDB / AlphaFold live connectors named in the PLAN are not
  implemented (only the UniProt live example is).
- The layer is additive: the M5 evidence-table builder still reads database records
  directly and does not (yet) go through connectors.

## Possible misleading artifacts
- `data_source` is *where the bytes came from* (fixture / cache / live), **not** whether
  a record is real — that is the separate `synthetic` flag (Open Targets association
  scores remain synthetic regardless of which connector serves them).
- A `data_source=cache` result means "served from the local `data/cache/` file", which
  was originally populated from the underlying source; it is not an independent
  confirmation.
- The connector counts (10 / 9 / 18) are inventory, **not** a quality metric.
- `data/cache/` files are gitignored, regenerable inspection artifacts, not a source of
  truth and not committed.
- The live connector's retry backoff numbers in tests come from an injected `sleep`; no
  real network timing is measured.

## Human feedback
<!-- Human will fill this later. -->
