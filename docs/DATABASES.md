# Database connectors

## TL;DR

A clean adapter layer (Milestone 6, **implemented**) with a common interface, a
required **fixture-backed** connector, a local read-through cache, transient-error
retry/backoff, and an explicit `data_source` provenance field (`fixture` / `cache` /
`live`) on every record. Live API connectors (PubMed / Europe PMC / OpenAlex /
UniProt / Open Targets / PDB / AlphaFold) are **optional, off by default, and never
required for tests**.

## Short explanation

```
BaseConnector                         (src/bioscientist_os/databases/base.py)
  ├── FixtureConnector   reads committed records      -> data_source=fixture   [required]
  ├── CachedConnector    read-through JSON cache       -> data_source=cache     (data/cache/, gitignored)
  └── LiveConnector      opt-in HTTP, off by default    -> data_source=live      [opt-in]
```

A *connector* hides **where** a record comes from behind one small interface
(`fetch(id) -> record | None`, `get`, `fetch_many`, `ids`) and guarantees that every
record it returns carries an honest `data_source`. So a memo or evidence table can
show whether a database link is committed, cached, or freshly fetched, instead of
trusting an opaque blob.

The three default connectors are addressed by short name:

| Name | Source | Record | Backed by |
|------|--------|--------|-----------|
| `uniprot` | `UniProt` | protein `DatabaseRecord` | `data/fixtures/uniprot/` |
| `opentargets` | `OpenTargets` | association `DatabaseRecord` | `data/fixtures/opentargets/` |
| `papers` | `papers` | `Paper` metadata | `data/fixtures/papers/` |

The `papers` connector is the offline stand-in for a PubMed / Europe PMC
paper-metadata connector; it serves the corpus `Paper`s by `paper_id`.

## Longer explanation

### Offline-first behavior and provenance

The default and test paths use only the fixture connectors. Every record they return
is stamped `data_source = fixture` at construction, so the contract holds regardless
of the inputs' incoming labels (`with_data_source` in `base.py`). `synthetic` is left
untouched — *fabricated-vs-real* is an orthogonal axis to *where the bytes came from*.

The **cache layer** (`CachedConnector`) wraps any connector and persists each fetched
record as canonical JSON under `data/cache/<source>/<id>.json` (gitignored). Its
provenance discipline is the point:

- a **cache hit** is stamped `data_source = cache` (the bytes came from the local
  file) and needs no inner connector at all — so a cache warmed from a live source
  keeps working offline, and repeated runs are deterministic;
- a **cache miss** returns the inner connector's own `data_source` (`fixture` /
  `live` — the bytes genuinely came from there just now) and writes a `cache`-stamped
  copy for next time.

So the very first fetch reports where the data really came from, and subsequent
fetches report `cache` — never the reverse. Cache files carry no timestamps or run
ids, so they are inspectable and stable.

### Retry / error handling

`call_with_retries` (in `base.py`) retries only **transient** failures
(`TransientConnectorError`: timeouts, 5xx, 429) with bounded exponential backoff,
wrapping an exhausted budget in a `ConnectorError`; a `PermanentConnectorError`
(bad request, disabled connector) is never retried. The `sleep` is injectable, so the
schedule is deterministic and tests run instantly without sleeping or networking. A
missing id is a `RecordNotFound` (from `get`) or `None` (from `fetch`) — distinct from
an operational failure, never a guess.

### Optional live connectors (opt-in, off by default)

`LiveConnector` is a thin, clearly-marked option. It is built so **no network call
can happen unless** it is constructed with `allow_network=True` *and* its transport
performs I/O: with the default `allow_network=False`, `fetch` raises a
`PermanentConnectorError` before the transport is ever consulted. The HTTP transport
is an injected callable, so the parse/retry/provenance logic is exercised entirely
**offline** with a mock transport in tests; the real default transport
(`urllib_transport`, stdlib `urllib`) is only reached when a caller opts in. One
concrete example ships — `uniprot_live_connector` — to show the shape of a real
adapter; it is best-effort and **never run in CI**.

### Targeted databases (fixture-modeled)

| Source | What it models | Status |
|--------|----------------|--------|
| PubMed / NCBI | paper metadata | fixture (`papers`); live optional |
| Europe PMC / OpenAlex | paper metadata | optional |
| UniProt | protein records | fixture (`uniprot`); live example shipped, opt-in |
| Open Targets | disease/gene/protein links | fixture (`opentargets`) |
| PDB / AlphaFold | structure links | optional, link-only |

### Licensing and honesty

Where a source's licensing or schema is uncertain, fixtures are **synthetic** and
marked `synthetic: true`. We do not redistribute bulk database content; fixtures are
small, illustrative, and labeled. See `data/fixtures/README.md`.

## Exact commands

```bash
# Build the database once (M2), then drive the connectors (offline, CPU-only):
biosci ingest data/fixtures --db results/raw/bioscientist.db

biosci db sources --db results/raw/bioscientist.db
biosci db list   --source uniprot --db results/raw/bioscientist.db
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db
biosci db lookup --source papers  --id biosci-paper-001 --db results/raw/bioscientist.db --json

# Demonstrate cache provenance: the first lookup reports the real source and writes a
# cache copy; the second reports data_source=cache (served from the local file).
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db --cache
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db --cache
```

The library entry points are `bioscientist_os.databases.load_connectors()` (from the
committed fixtures) and `open_connectors(db_path)` (from an ingested database); both
return a `ConnectorRegistry`.

## Limitations

- Live connectors are best-effort and never run in CI; only the fixture/cache path
  carries correctness/reproducibility guarantees. The shipped UniProt live parser is
  a minimal, defensive example, not a complete UniProt client.
- Fixture coverage is small and theme-focused (senescence/longevity/autophagy).
- No bulk download, no rate-limit-heavy crawling, no credentialed endpoints.
- The connector layer serves *observed metadata*; it makes no claim, relation, or
  biological assertion (that discipline lives in the evidence table; see
  `docs/SAFETY.md`).
