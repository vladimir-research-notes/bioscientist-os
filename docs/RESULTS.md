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
| 4 — entity and claim extraction baseline | Done | `python3 -m pytest -q` → **119 passed** |

The 119 tests are the Milestone-0 contract/import/CLI-smoke checks (20), the
Milestone-1 schema and fixture checks (30), the Milestone-2 storage and
ingestion checks (17), the Milestone-3 search and topic checks (28), and the
Milestone-4 extraction checks (24): schema JSON round-trips, the enforced
provenance/epistemic/validation rules, fixture loading, ingestion into SQLite
(count checks, idempotent re-ingest, two-build determinism, exact round-trip,
schema-validation-on-ingest), search and topic grouping (tokenizer behavior,
BM25F scoring with `score == Σ contributions`, field weighting, tiny labeled
queries, TF-IDF cosine self-similarity, topic partition/monotonicity), and now
extraction (span-exact tokenizer/sentence splitter, dictionary build from
fixtures, longest-match recognition, span round-trips against the abstract, the
relation templates, the transparent confidence, determinism, and the CLI). No
evidence-table or *evaluation* numbers exist yet; those land in Milestones 5–8.

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

### Evidence table / provenance (Milestones 5, 8)

| Metric | Value | Denominator |
|--------|-------|-------------|
| evidence rows generated | _pending_ | |
| provenance coverage | _pending_ | |

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
