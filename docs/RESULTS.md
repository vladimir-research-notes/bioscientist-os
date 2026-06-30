# Results

## TL;DR

This document holds **measured** results (counts, metrics, figures) produced by
the milestones. It is intentionally near-empty in the scaffold commit: there are
no functional results to report yet. Each milestone that produces measurable
output appends to this file with exact commands and denominators.

> Do not cite any number here until the corresponding milestone has landed and
> the table below is populated. Empty cells mean *not yet measured*, not zero.

## Build / test status

The only measured results so far concern the build itself, not the pipeline:

| Milestone | Status | Offline test suite |
|-----------|--------|--------------------|
| 0 — package skeleton and runnable CLI | Done | (subsumed) |
| 1 — data schemas and small fixtures | Done | (subsumed) |
| 2 — ingestion and local storage | Done | (subsumed) |
| 3 — search and topic grouping | Done | (subsumed) |
| 4 — entity and claim extraction baseline | Done | (subsumed) |
| 5 — evidence table builder | Done | (subsumed) |
| 6 — database connector layer | Done | `python3 -m pytest -q` → **178 passed** |

The 178 tests are the Milestone-0 contract/import/CLI-smoke checks (20), the
Milestone-1 schema and fixture checks (30), the Milestone-2 storage and
ingestion checks (17), the Milestone-3 search and topic checks (28), the
Milestone-4 extraction checks (24), the Milestone-5 evidence-table checks
(24), and the Milestone-6 connector checks (35): schema JSON round-trips, the
enforced provenance/epistemic/validation rules, fixture loading, ingestion into
SQLite (count checks, idempotent re-ingest, two-build determinism, exact
round-trip, schema-validation-on-ingest), search and topic grouping (tokenizer
behavior, BM25F scoring with `score == Σ contributions`, field weighting, tiny
labeled queries, TF-IDF cosine self-similarity, topic partition/monotonicity),
extraction (span-exact tokenizer/sentence splitter, dictionary build from
fixtures, longest-match recognition, span round-trips against the abstract, the
relation templates, the transparent confidence, determinism, and the CLI), the
evidence table (the support/conflict/unknown cue heuristic, question resolution,
the relevance filter, span round-trips, 100% provenance coverage, column
completeness, determinism, and the CLI), and now the connector layer (fixture
lookup with `data_source=fixture`, missing-id `None`/`RecordNotFound`, the
registry, cache miss→`fixture`/hit→`cache` with offline-first serving and
canonical round-trip, transient-only retry with deterministic backoff, the
opt-in live connector exercised offline with a mock transport, and the
`biosci db` CLI). No *evaluation* numbers exist yet; those land in Milestone 8.

### Fixtures (Milestone 1)

The committed corpus loads and validates via
`python3 -c "from bioscientist_os.fixtures import load_all; print(load_all().summary())"`:

| Fixture set | Count | `synthetic` | Notes |
|-------------|-------|-------------|-------|
| papers (`data/fixtures/papers/papers.json`) | 18 | `true` (all) | fabricated abstracts; test-prefix DOIs (`10.0000/`) |
| proteins (`data/fixtures/uniprot/proteins.json`) | 10 | `false` (all) | modeled on real UniProt accessions; condensed function text |
| associations (`data/fixtures/opentargets/associations.json`) | 9 | `true` (all) | real gene symbols, **fabricated** scores, synthetic disease ids |
| research questions (`data/fixtures/questions.json`) | 3 | n/a | seeds for evidence tables / memos |

These counts describe the fixture set, not pipeline performance. Theme:
cellular senescence / longevity / autophagy. Papers 006 and 007 deliberately
disagree on whether autophagy promotes or restrains senescence, to give later
support/conflict logic real material.

## Result tables (populated by milestones)

### Ingestion (Milestone 2)

Produced by `python3 scripts/01_ingest_fixtures.py` (or
`biosci ingest data/fixtures --db results/raw/bioscientist.db`), then inspected
with `biosci stats --db results/raw/bioscientist.db`. The database is gitignored
and reproducible from the committed fixtures.

| Quantity | Value |
|----------|-------|
| paper fixtures ingested (`papers`) | 18 |
| uniprot fixtures ingested (`database_records`, source `UniProt`) | 10 |
| opentargets link fixtures ingested (`database_records`, source `OpenTargets`) | 9 |
| research questions ingested | 3 |
| total rows | 40 |
| first ingest writes | 40 inserted, 0 updated |
| idempotent re-ingest writes | 0 inserted, 40 updated (no new rows) |
| two-build content digest (sha256) | identical (`f040627…5123da94`) |

Idempotency is verified by re-ingesting into the same database (counts and
content digest unchanged); deterministic creation is verified by ingesting into
two fresh databases and comparing their content digests. The digest is a SHA-256
over the canonical, primary-key-sorted serialization of every data row, so it is
independent of insertion order and on-disk layout. Every ingested row is
*observed metadata* with `data_source = fixture`; no claims or relations are
produced at ingestion.

### Search and topic grouping (Milestone 3)

Produced by `python3 scripts/02_build_index.py` (or `biosci search` /
`biosci topics`). The index is recomputed in memory from the ingested database
each run; building it is deterministic.

Corpus index over the 18 ingested papers:

| Quantity | Value |
|----------|-------|
| papers indexed | 18 |
| vocabulary (distinct terms, all fields) | 436 |
| avg field length (title / keywords / abstract) | 9.7 / 5.5 / 45.2 tokens |
| BM25F field weights (title / keywords / abstract) | 3.0 / 2.0 / 1.0 |
| BM25 parameters | `k1 = 1.5`, `b = 0.75` |

Search sanity on **8 single-target, hand-labeled queries** (each query has one
"clearly correct" paper; assertion is top-_k_ membership):

| Metric | Value | Denominator |
|--------|-------|-------------|
| expected paper at rank 1 (`hit@1`) | 0.88 | 7 / 8 |
| expected paper in top 3 (`hit@3`) | 1.00 | 8 / 8 |
| expected paper in top 5 (`hit@5`) | 1.00 | 8 / 8 |

This is a sanity check on a tiny synthetic corpus, **not** a recall benchmark;
the rigorous evaluation with denominators and confidence intervals is Milestone 8.

Topic grouping (single-link cosine clustering) at the default threshold `0.15`:

| Quantity | Value |
|----------|-------|
| groups | 10 (4 multi-paper, 6 singletons) |
| multi-paper groups (by label terms) | SASP/secretion (4); senescence markers (3); autophagy/mTOR/longevity (3); senolytics (2) |
| determinism | identical grouping on every build; group count is monotone non-decreasing in the threshold |

Group labels are the most distinctive terms of each group; they describe a group
and are **not** asserted topics of the field.

### Entity / claim extraction (Milestone 4)

Produced by `python3 scripts/03_extract_claims.py` (or `biosci extract --db ...`).
The dictionary is built from the ingested database records (10 UniProt protein
records + 9 Open Targets associations that add surface synonyms) plus a small,
explicit curated seed of 16 process / phenotype / chemical terms; extraction reads
the **abstracts only**, and is deterministic (`claims.json` is byte-identical
across runs).

| Quantity | Value |
|----------|-------|
| dictionary entities | 26 (10 protein, 9 process, 6 other, 1 chemical) |
| dictionary surface forms | 61 |
| papers processed | 18 |
| entity mentions recognized (`BiomedicalEntity` rows) | 63 |
| claim sentences extracted (`Claim` rows) | 42 |
| claims with a subject–relation–object triple | 15 |
| span-round-trip failures (`abstract[start:end] == snippet`) | 0 / 105 |

Claim-confidence distribution (transparent additive salience, see
`docs/METHODOLOGY.md` and `evidence/extract.py`):

| Confidence | Claims | Composition |
|-----------|--------|-------------|
| 0.35 | 9 | one entity, no triple, no reporting cue |
| 0.45 | 5 | one entity + reporting cue |
| 0.60 | 8 | ≥2 entities |
| 0.70 | 5 | ≥2 entities + reporting cue |
| 0.90 | 11 | triple + ≥2 entities |
| 1.00 | 4 | triple + ≥2 entities + reporting cue |

The designed conflict pair surfaces: paper-006 yields `autophagy --promotes-->
cellular senescence` while paper-007 yields `autophagy --restrains--> cellular
senescence` — material the Milestone-5 support/conflict logic will use.

These are **extraction counts and behavior**, not quality metrics. Precision /
recall against tiny gold labels (with denominators and Wilson intervals) is
Milestone 8:

| Metric | Value (95% Wilson CI) | Denominator |
|--------|-----------------------|-------------|
| entity precision | _pending (M8)_ | |
| entity recall | _pending (M8)_ | |
| claim sanity pass rate | _pending (M8)_ | |

### Evidence table / provenance (Milestone 5)

Produced by `python3 scripts/04_build_evidence_table.py` (or `biosci evidence
--question "..." --db ... --out ...`). One table is built per stored research
question: each kept claim (one that mentions ≥1 dictionary-recognized question
entity) becomes a row carrying full per-cell provenance, database links
(UniProt/HGNC xrefs + Open Targets associations), and a heuristic
support/conflict/unknown label. Assembly is deterministic
(`evidence_tables.json` is byte-identical across runs).

| Research question | Rows | support / conflict / unknown | Provenance coverage |
|-------------------|------|------------------------------|---------------------|
| `rq-senescence-inflammation` | 31 | 17 / 6 / 8 | 100% (31/31) |
| `rq-autophagy-senescence` | 29 | 15 / 6 / 8 | 100% (29/29) |
| `rq-longevity-pathways` | 8 | 4 / 1 / 3 | 100% (8/8) |

Provenance coverage is the fraction of rows whose provenance names both a paper
and a source snippet; it is 100% by construction, since a row is only emitted
from a claim that already has both (the test suite asserts this, not just the
script). The support/conflict/unknown label is a heuristic **textual** signal
(`rule:support-cues`): a strong negation cue → conflict, an asserted relationship
(a relation triple or a support cue) → support, otherwise unknown. It reads one
sentence's phrasing and is **not** a biological or clinical verdict; in
particular it does not detect cross-paper *directional* conflict — e.g. paper-006
(`autophagy --promotes--> senescence`) and paper-007 (`autophagy --restrains-->
senescence`) both read as `support` per row. These are **builder counts and
behavior**, not quality metrics; support-label precision/recall against gold
labels (with denominators and Wilson intervals) is Milestone 8.

### Database connectors (Milestone 6)

Produced by `biosci db sources / list / lookup` over the ingested database (or the
library entry points `load_connectors()` / `open_connectors(db)`). The connectors are
fixture-backed and offline; the table is connector inventory, **not** a quality
metric.

| Connector | Source | Record type | Records | Default `data_source` |
|-----------|--------|-------------|---------|-----------------------|
| `uniprot` | `UniProt` | protein | 10 | `fixture` |
| `opentargets` | `OpenTargets` | association | 9 | `fixture` |
| `papers` | `papers` | paper metadata | 18 | `fixture` |

Behavior pinned by the 35 connector tests (no network, no real sleeping):

- every fixture lookup is stamped `data_source = fixture`; a missing id is `None`
  (`fetch`) or `RecordNotFound` (`get`), never a guess;
- the cache makes provenance honest and offline-first: a first lookup reports the
  real source and writes a `data/cache/<source>/<id>.json` copy; a second lookup of
  the same id reports `data_source = cache` and is served from the local file with no
  inner call (a cache warmed from a source still serves with the inner connector
  gone). Cache files are canonical JSON and round-trip back into the typed model;
- `call_with_retries` retries only transient failures (deterministic injected
  backoff `[0.5, 1.0]` for two retries), wraps an exhausted budget in a
  `ConnectorError`, and never retries a permanent error;
- the live connector is **off by default** (it raises before any transport call) and,
  with an injected mock transport, parses, retries, 404→`None`, and stamps
  `data_source = live`.

The connector layer serves *observed metadata* only; it makes no claim, relation, or
biological assertion.

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
