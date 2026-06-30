# Milestone 6 — Database connector layer

## Summary

The workbench gains an **offline-first database-connector layer**: a clean adapter
that hides *where* a record comes from behind one small interface and keeps an honest
`data_source` provenance (`fixture` / `cache` / `live`) on every record. The default
and test paths use only the required **fixture** connectors; a gitignored
read-through **cache** makes repeated runs deterministic and network-free; **live**
connectors are opt-in, off by default, and never required for tests. Connectors serve
*observed metadata* — no claim, relation, or biological assertion is made here.

## Deliverables

- **`src/bioscientist_os/databases/base.py`** — the contract:
  - `BaseConnector[T]` (PEP 695 generic, `T` bound to a record model) — `fetch(id) ->
    record | None`, `get` (raise `RecordNotFound`), `fetch_many`, `ids`, `in`, `len`,
    `describe`;
  - the error hierarchy: `ConnectorError` with `TransientConnectorError` /
    `PermanentConnectorError` subclasses, and `RecordNotFound` (a `KeyError`,
    distinct from an operational failure);
  - `with_data_source(record, source)` — provenance stamping (copy only if it would
    change; `synthetic` untouched);
  - `call_with_retries(fn, …)` — bounded exponential backoff that retries **only**
    transient errors, with an **injectable `sleep`** (deterministic, no real
    sleeping in tests) and a wrapped-on-exhaustion `ConnectorError`.
- **`src/bioscientist_os/databases/fixture.py`** — `FixtureConnector` (in-memory,
  stamps `fixture`, first-id-wins on collision) and the `uniprot` / `opentargets` /
  `papers` factories + `build_fixture_connectors`. The `papers` connector is the
  offline stand-in for a PubMed / Europe PMC paper-metadata connector.
- **`src/bioscientist_os/databases/cache.py`** — `CachedConnector`: read-through JSON
  cache under `data/cache/<source>/<id>.json` (gitignored, canonical JSON, no
  timestamps). Cache **hit** → `data_source=cache` (served from the file, no inner
  call); cache **miss** → the inner source's `data_source`, plus a `cache`-stamped
  copy written for next time. `is_cached` / `cached_ids` for inspection.
- **`src/bioscientist_os/databases/live.py`** — `LiveConnector` (opt-in): with
  `allow_network=False` (default) `fetch` raises **before** any transport call; the
  HTTP transport is injected so the parse/retry/provenance logic is tested offline
  with a mock. Ships `urllib_transport` (stdlib, opt-in) and one best-effort
  `uniprot_live_connector` example (never run in CI). A live source is not
  enumerable (`ids` raises).
- **`src/bioscientist_os/databases/registry.py`** — `ConnectorRegistry`
  (`names` / `get` / `describe`) with `load_connectors()` (from the committed
  fixtures) and `open_connectors(db)` (from an ingested database, with the same
  not-a-database guard as the other subcommands).
- **CLI** (`cli.py`): a `biosci db` sub-app — `db sources`, `db list --source <name>`,
  `db lookup --source <name> --id <id> [--cache] [--cache-dir] [--json]`; every output
  surfaces the `data_source` provenance. `info` status updated to Milestones 0–6.
- **Tests**: `tests/test_connectors.py` (35) — 178 total, all offline.

## Design notes / decisions

- **Provenance is stamped, never passed through.** A connector enforces its own
  `data_source` rather than trusting an object's incoming label. This is what makes
  the cache's two-state behavior honest: the first fetch reports where the bytes
  really came from; only a subsequent, file-served fetch reports `cache`. The reverse
  (claiming `cache` for a record that was just fetched live) never happens.
- **`synthetic` is orthogonal to `data_source`.** Stamping the source never touches
  `synthetic` — *fabricated-vs-real* and *where-the-bytes-came-from* are independent
  axes, both surfaced.
- **Retry is transient-only and deterministic.** Only `TransientConnectorError`
  (timeouts / 5xx / 429) is retried; a `PermanentConnectorError` propagates on the
  first raise. The `sleep` is injected, so backoff (`[0.5, 1.0]` for two retries) is
  asserted exactly and tests never sleep or open a socket.
- **Live is off by default, by construction.** No network call can happen unless the
  connector is built with `allow_network=True` *and* its transport performs I/O. The
  transport is injected, so the live logic is fully exercised offline with a mock;
  the shipped UniProt example is a minimal, defensive illustration, not a complete
  client, and is never run in CI.
- **Papers as a connector.** `Paper` carries `data_source`, so the same generic
  interface serves paper metadata (`papers`) alongside the `DatabaseRecord` sources
  (`uniprot`, `opentargets`) — satisfying the PLAN's "fixture-backed UniProt-style and
  paper-metadata connectors" minimum without a parallel type.
- **Additive, not a refactor.** M5's evidence-table builder still reads database
  records directly; the connector layer is new infrastructure (with its own CLI and
  tests) that later milestones (the link graph in M7, the memo in M9) can build on.

## Validation

```bash
python3 -m pytest -q                                  # 178 passed (offline)
python3 scripts/01_ingest_fixtures.py --reset         # -> results/raw/bioscientist.db
biosci db sources --db results/raw/bioscientist.db
biosci db list   --source uniprot --db results/raw/bioscientist.db
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db
biosci db lookup --source papers  --id biosci-paper-001 --db results/raw/bioscientist.db --json
# cache provenance: first lookup = fixture (writes a copy), second = cache
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db --cache --cache-dir /tmp/c
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db --cache --cache-dir /tmp/c
ruff check src/bioscientist_os/databases/ src/bioscientist_os/cli.py tests/test_connectors.py  # clean
```

Measured on the committed fixtures (connector **inventory**, not a quality metric):

| Connector | Source | Record type | Records | Default `data_source` |
|-----------|--------|-------------|---------|-----------------------|
| `uniprot` | `UniProt` | protein | 10 | `fixture` |
| `opentargets` | `OpenTargets` | association | 9 | `fixture` |
| `papers` | `papers` | paper metadata | 18 | `fixture` |

The 35 connector tests pin: fixture lookup + `fixture` stamping, missing-id
`None`/`RecordNotFound`, the registry and `load`/`open` agreement, cache
miss→`fixture`/hit→`cache` with offline-first serving and canonical round-trip,
transient-only retry with `[0.5, 1.0]` backoff and exhaustion wrapping, the opt-in
live connector (disabled-by-default, parse + `live` stamp, 404→`None`,
retry/exhaustion, non-enumerable) via a mock transport, and the `biosci db` CLI
(sources/list/lookup, cache round-trip, error exits). All offline; no network, no
paid API, no GPU.

## Status

**Complete.** Next: **Milestone 7 — Visualizations** (literature timeline, topic-cluster
summary, claim/evidence matrix, entity/database-link graph, support-vs-conflict table;
matplotlib optional, figure tests skipped when it is absent).
