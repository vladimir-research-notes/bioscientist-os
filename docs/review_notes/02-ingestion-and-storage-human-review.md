# Human review: Milestone 2 — Ingestion and local storage

## TL;DR
The committed fixtures now ingest into a local SQLite database via a dedicated
storage layer (`SQLiteStore`) and an `ingest_fixtures()` pipeline, exposed as
`biosci ingest` / `biosci stats`. Ingest is idempotent (UPSERT by stable id) and
the database is content-deterministic (a SHA-256 digest is identical across
builds). Result: 18 papers, 10 proteins, 9 associations, 3 questions = 40 rows.
67 offline tests pass. No search/extraction/evidence yet — that is Milestone 3.

## What changed
- Added `src/bioscientist_os/storage/sqlite_store.py` (`SQLiteStore`): three data
  tables + `ingest_meta`, canonical-JSON sub-fields, idempotent UPSERTs, exact
  round-trip readers, `content_digest()`, and aggregate views for `stats`.
- Added `src/bioscientist_os/ingest/pipeline.py` (`ingest_fixtures`,
  `IngestReport`): load+validate before writing, upsert, report.
- Added `biosci ingest` and `biosci stats` CLI commands and
  `scripts/01_ingest_fixtures.py`.
- Added `tests/test_storage.py` and `tests/test_ingest.py` (17 new tests).
- Added a ruff `extend-immutable-calls` entry for Typer in `pyproject.toml`.
- Updated docs (`RESULTS.md`, `REPRODUCIBILITY.md`) and the website
  (`ingestion`, `milestones`, `results`, `architecture`, `index`).

## Commands run
- `python3 -m pytest -q` → **67 passed** (offline).
- `python3 scripts/01_ingest_fixtures.py --reset` →
  `40 records -> results/raw/bioscientist.db` (40 inserted, 0 updated).
- `biosci stats --db results/raw/bioscientist.db` → 18 papers; 19 database
  records (UniProt/protein 10, OpenTargets/association 9); 3 research questions;
  one content digest.
- `ruff check` on the new files → clean.

## Test status
67 passed (50 prior + 17 new). The new tests assert: ingestion counts
(18/10/9/3), idempotent re-ingest (0 inserted, 40 updated, unchanged digest),
two-build determinism (equal digests), exact round-trip back into the schemas,
schema-validation-on-ingest (malformed corpus aborts with no partial DB), the
`--reset` rebuild, the digest's insertion-order independence and
content-sensitivity, the `(source, record_type)` breakdown, and the
`biosci ingest`/`biosci stats` CLI (including the error on a non-database file).

## Known limitations
- **Determinism is content-level, not byte-level.** Two builds from the same
  fixtures share an identical `content_digest`, but the raw `.db` bytes may differ
  across libsqlite versions/platforms. The digest is the guarantee; the file is
  not asserted byte-identical.
- **Dedup is by stable id only.** Re-ingest is duplicate-safe, but two fixtures
  describing the *same* paper under different ids (or different DOI/PMID) would
  both be stored. Near-duplicate detection is deferred.
- **Tiny, partly-synthetic corpus.** The counts (18/10/9/3) describe the fixture
  set, not pipeline performance or biology. All paper abstracts and all
  association scores are fabricated (see `data/fixtures/README.md`).
- **No DuckDB backend.** It is listed as optional in the plan but is not
  implemented; SQLite is the only backend.
- **Storage holds observed metadata only.** Entities, claims, and evidence tables
  are *not* persisted yet; their tables do not exist until later milestones.

## Possible misleading artifacts
- **"40 rows ingested" is not a measurement of anything biological.** It is the
  size of a hand-built fixture set chosen to exercise the pipeline.
- **The content digest proves reproducibility, not correctness.** Identical
  digests mean two builds hold the same rows; they say nothing about whether the
  fixtures are accurate.
- **`biosci stats` shows a non-clinical data source.** The counts and breakdown
  are corpus bookkeeping, not evidence; nothing here is a claim, relation, or
  clinical statement.
- **The generated `results/raw/bioscientist.db` is gitignored.** If you do not see
  it after checkout, that is expected — run the ingest command to regenerate it.

## Human feedback
<!-- Human will fill this later. -->
