# Milestone 2 — Ingestion and local storage

## Summary

The committed fixture corpus now ingests into a local SQLite database through a
dedicated storage layer. `bioscientist-os` gains a `SQLiteStore` backend, an
`ingest_fixtures()` pipeline, the `biosci ingest` / `biosci stats` CLI commands,
and a thin `scripts/01_ingest_fixtures.py` wrapper. Writes are idempotent and the
database is content-deterministic. No search, extraction, or evidence logic yet —
those begin at Milestone 3.

## Deliverables

- **`src/bioscientist_os/storage/sqlite_store.py`** — `SQLiteStore`, the default
  stdlib `sqlite3` backend:
  - Three data tables (`papers`, `database_records`, `research_questions`) plus a
    small `ingest_meta` table; one row per schema object; structured sub-fields
    (authors, keywords, external ids, record payloads) stored as canonical
    (sorted-key, compact) JSON so rows round-trip back into the exact pydantic
    models.
  - Idempotent UPSERT writes keyed by stable id (`paper_id`;
    `(source, record_id)`; `question_id`); each `upsert_*` returns whether the row
    was newly inserted.
  - `content_digest()` — a SHA-256 over every data row in primary-key order
    (independent of insertion order / on-disk layout), excluding `ingest_meta`, so
    the digest is a pure function of the ingested content + `SCHEMA_VERSION`.
  - Round-trip readers (`iter_papers` / `iter_database_records` /
    `iter_research_questions`) and aggregate views (`table_counts`,
    `record_breakdown`, `meta`, `is_initialized`).
- **`src/bioscientist_os/ingest/pipeline.py`** — `ingest_fixtures(fixtures_dir,
  *, db_path, reset=False)` and the `IngestReport` dataclass. Loads + validates
  every fixture **before** touching disk (a malformed corpus aborts with no
  partial database), upserts each record, and reports counts + inserted/updated +
  digest.
- **CLI** (`src/bioscientist_os/cli.py`): `biosci ingest <dir> --db <path>
  [--reset]` and `biosci stats --db <path> [--json]`. Both surface the epistemic
  level (observed metadata) and the non-clinical stance.
- **`scripts/01_ingest_fixtures.py`** — install-free wrapper (defaults to
  `data/fixtures` → `results/raw/bioscientist.db`).
- **Tests**: `tests/test_storage.py` (8) and `tests/test_ingest.py` (9) — 17 new,
  67 total, all offline.
- Config: added `tool.ruff.lint.flake8-bugbear.extend-immutable-calls` for
  `typer.Option`/`typer.Argument` so the Typer idiom (calls in parameter defaults)
  is not a false-positive B008 — needed now that CLI commands take `Path` options.
- Docs + website: `docs/RESULTS.md`, `docs/REPRODUCIBILITY.md`, and
  `site/{ingestion,milestones,results,architecture,index}.html` updated to the
  delivered state (M2 → Done).

## Design notes / decisions

- **Storage vs. ingestion split.** `SQLiteStore` only persists and reads typed
  objects; it does not decide *what* to write. The `ingest/` pipeline orchestrates
  load → validate → upsert → report. This keeps the storage backend reusable by
  later milestones (entities, claims, evidence tables).
- **Determinism by construction.** No timestamps or run ids are written to data
  tables; sub-fields are canonical JSON; reads and the digest sort by primary key.
  The robust guarantee is *content* determinism (equal `content_digest` across
  builds), not byte-identical files — libsqlite versions can differ on page
  layout. The honest claim is stated as such in the docs and the page.
- **Idempotency over dedup.** Re-ingest is duplicate-safe via UPSERT keyed by
  stable id. Near-duplicate detection (same paper via different DOI/PMID, title
  hashing) is explicitly **deferred** and called out as an open question.
- **Validate before write.** `fixtures.load_all` constructs pydantic models first,
  so a bad corpus raises `FixtureError` before any file is created — no partial
  database is left behind (tested).
- **One records table.** UniProt-style proteins and Open Targets-style
  associations are both `DatabaseRecord`; they share `database_records` keyed by
  `(source, record_id)`, with `biosci stats` reporting the per-source breakdown.

## Validation

```bash
python3 -m pytest -q                                  # 67 passed (offline)
python3 scripts/01_ingest_fixtures.py --reset         # -> results/raw/bioscientist.db
biosci stats --db results/raw/bioscientist.db         # 18 papers, 19 records (10+9), 3 questions
ruff check src/bioscientist_os/storage src/bioscientist_os/ingest \
           src/bioscientist_os/cli.py scripts/01_ingest_fixtures.py \
           tests/test_storage.py tests/test_ingest.py # clean
```

Measured: 18 papers / 10 proteins / 9 associations / 3 questions = 40 rows; first
ingest 40 inserted / 0 updated; idempotent re-ingest 0 inserted / 40 updated with
an unchanged content digest; two fresh builds share the same digest
(`f040627…5123da94`). All offline; no network, no paid API, no GPU. The generated
`.db` is gitignored under `results/`.

## Status

**Complete.** Next: **Milestone 3 — Search and topic grouping** (a CPU-only
lexical/BM25-like baseline over the ingested corpus, optional TF-IDF, simple topic
grouping, and per-result match explanations).
