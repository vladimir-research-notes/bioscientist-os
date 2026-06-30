# Commit note: Milestone 6 — Add offline-first database connector layer

## Intent
Give the workbench a clean adapter layer that hides *where* a record comes from
behind one interface and keeps an honest `data_source` provenance (`fixture` /
`cache` / `live`) on every record — so a downstream evidence cell or memo can show
whether a database link is committed, cached, or freshly fetched. Offline-first by
default: fixture connectors are required, the cache is gitignored and deterministic,
and live connectors are opt-in and never required for tests.

## What the commit contains
- `src/bioscientist_os/databases/base.py`: `BaseConnector[T]` (PEP 695 generic), the
  connector error hierarchy (`ConnectorError` + transient/permanent + `RecordNotFound`),
  `with_data_source` provenance stamping, and `call_with_retries` (transient-only,
  injectable-sleep exponential backoff).
- `src/bioscientist_os/databases/fixture.py`: `FixtureConnector` + the `uniprot` /
  `opentargets` / `papers` factories and `build_fixture_connectors`.
- `src/bioscientist_os/databases/cache.py`: `CachedConnector` — read-through JSON cache
  under `data/cache/` (gitignored); hit → `cache`, miss → inner source (+ writes a
  `cache` copy); offline-first serving; `is_cached` / `cached_ids`.
- `src/bioscientist_os/databases/live.py`: `LiveConnector` (opt-in, off by default,
  injected transport), `urllib_transport`, and a best-effort `uniprot_live_connector`
  example (never run in CI).
- `src/bioscientist_os/databases/registry.py`: `ConnectorRegistry`, `load_connectors`
  (fixtures), `open_connectors` (ingested db, not-a-database guard).
- `src/bioscientist_os/databases/__init__.py`: re-export the M6 surface.
- `src/bioscientist_os/cli.py`: `biosci db` sub-app (`sources`, `list`, `lookup` with
  `--cache` / `--cache-dir` / `--json`), each surfacing `data_source`; `info` and the
  module docstring updated to Milestones 0–6.
- `tests/test_connectors.py` (35): provenance stamping, fixture lookup + missing-id
  handling, the registry and `load`/`open` agreement, the cache (miss→`fixture`,
  hit→`cache`, offline-first, canonical round-trip, no-write-on-miss), `call_with_retries`
  (success/retry/exhaustion/permanent), the live connector via a mock transport
  (disabled-by-default, parse + `live` stamp, 404→`None`, retry, non-enumerable), and the
  CLI. 178 total, all offline.
- Docs + website: milestone/commit/review notes; `DATABASES.md` (implemented),
  `RESULTS.md`, `REPRODUCIBILITY.md`; `site/` (`databases` → Done with the interface,
  cache/retry/live, and commands; `milestones`/`index`/`architecture`/`results` updated
  to M6 → Done and 178 tests).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. Live connectors are off by default
and exercised only via a mock transport — no socket is opened in tests. The only
generated artifacts are under `results/` and `data/cache/`, both gitignored and
regenerable; neither is staged. No secrets, caches, virtualenvs, weights, or large data
are staged. The connector layer serves *observed metadata* only — no claim, relation,
or biological/clinical assertion — and every record carries its `data_source`
provenance. `ruff check` is clean on the new/changed files; the one pre-existing E501 in
`tests/test_repo_contract.py` is unrelated to this milestone and left untouched. Working
tree is clean after commit.
