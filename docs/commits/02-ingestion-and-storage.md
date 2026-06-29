# Commit note: Milestone 2 — Add fixture ingestion and local storage

## Intent
Give `bioscientist-os` a persistence layer: ingest the committed fixtures into a
local SQLite database deterministically and idempotently, so every later
milestone (search, extraction, evidence tables) reads from one auditable store
instead of re-parsing JSON. No search/extraction logic in this commit.

## What the commit contains
- `src/bioscientist_os/storage/sqlite_store.py`: `SQLiteStore`, a stdlib
  `sqlite3` backend. Tables `papers`, `database_records`, `research_questions`
  (+ `ingest_meta`); one row per schema object with structured sub-fields as
  canonical sorted-key JSON; idempotent UPSERTs keyed by stable id; round-trip
  readers; `content_digest()` (SHA-256 over rows in primary-key order) for
  reproducibility; `table_counts`/`record_breakdown`/`meta`/`is_initialized`.
- `src/bioscientist_os/ingest/pipeline.py`: `ingest_fixtures()` +
  `IngestReport`. Loads and validates fixtures *before* touching disk, upserts
  each record, and reports counts + inserted/updated + digest.
- `src/bioscientist_os/cli.py`: `biosci ingest <dir> --db <path> [--reset]` and
  `biosci stats --db <path> [--json]`; both surface the observed-metadata
  epistemic level and the non-clinical stance.
- `scripts/01_ingest_fixtures.py`: install-free wrapper (defaults
  `data/fixtures` → `results/raw/bioscientist.db`).
- `tests/test_storage.py` (8) and `tests/test_ingest.py` (9): 17 new tests; 67
  total, all offline. Cover count checks, idempotent re-ingest, two-build
  determinism, exact round-trip, schema-validation-on-ingest, and the CLI.
- `pyproject.toml`: ruff `extend-immutable-calls = ["typer.Option",
  "typer.Argument"]` so Typer's call-in-default idiom is not a B008 false
  positive (CLI commands now take `Path` options).
- Docs + website: `docs/RESULTS.md`, `docs/REPRODUCIBILITY.md`, and
  `site/{ingestion,milestones,results,architecture,index}.html` updated to the
  delivered state (M2 → Done).

## Why it is safe to commit
CPU-only, offline, no network or paid API. The only generated artifact is the
SQLite database under `results/` (gitignored, reproducible from fixtures); it is
**not** staged. No secrets, caches, virtualenvs, weights, or large data are
staged (`.venv/`, `*.egg-info/`, `__pycache__/`, `results/` remain gitignored).
Ingested rows are observed metadata (`data_source = fixture`); no claims,
relations, or clinical content are produced. Working tree is clean after commit.
