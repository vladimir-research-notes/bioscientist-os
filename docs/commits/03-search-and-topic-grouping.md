# Commit note: Milestone 3 — Add lexical search and topic grouping

## Intent
Make the ingested corpus searchable and groupable on CPU, offline, with the
*explanation* as a first-class output: a scientist must see which terms matched,
in which fields, and how much each contributed, and must be able to inspect how
papers were grouped into topics. No claims or relations are produced — search and
topics rank/group observed-metadata papers only.

## What the commit contains
- `src/bioscientist_os/search/tokenize.py`: transparent tokenizer (lowercase,
  internal hyphens preserved so `IL-6`/`p16INK4a`/`ATG7-dependent` stay single
  tokens), a small documented stop list (TF-IDF/topics only), and BM25 / TF-IDF
  idf helpers. No stemming or synonym expansion.
- `src/bioscientist_os/search/index.py`: `SearchIndex` — field-aware (title 3.0 /
  keywords 2.0 / abstract 1.0) BM25F (`k1=1.5`, `b=0.75`) with a per-term,
  per-field score breakdown (`score == Σ contributions`); smoothed L2-normalized
  TF-IDF vectors + cosine; optional `tfidf_search`; `corpus_stats`; `load_index`.
- `src/bioscientist_os/search/topics.py`: `group_topics` — single-link clustering
  as connected components of a cosine-threshold graph (default `0.15`), labeled by
  top-TF-IDF-mass terms; deterministic and monotone in the threshold (uses
  `networkx`, already a dependency).
- `src/bioscientist_os/search/model.py`: frozen result dataclasses
  (`TermMatch`, `SearchHit`, `SearchResponse`, `TopicGroup`, `TopicReport`) with
  `to_dict()`.
- `src/bioscientist_os/cli.py`: `biosci search "<query>" --db <path>
  [--limit N] [--method bm25|tfidf] [--explain] [--json]` and `biosci topics
  --db <path> [--threshold T] [--top-terms K] [--json]`; `info` updated to M0–3.
- `scripts/02_build_index.py`: install-free wrapper; prints corpus stats, the
  topic grouping, and demo-query hits, and writes
  `results/processed/search_index.json` (gitignored, regenerable).
- `tests/test_search.py` (28): tokenizer, BM25F scoring/explanation/determinism,
  field weighting, tiny labeled queries, TF-IDF cosine, topic
  partition/monotonicity/labels, and the CLI. 95 total, all offline.
- Docs + website: milestone/commit/review notes; `RESULTS.md`,
  `REPRODUCIBILITY.md`, `ARCHITECTURE.md`; `site/` (new `search.html`, nav link on
  every page, `milestones`/`index`/`architecture`/`results` updated to M3 → Done).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The only generated artifacts
are under `results/` (the SQLite database and `search_index.json`), which is
gitignored and regenerable from the committed fixtures; they are **not** staged.
No secrets, caches, virtualenvs, weights, or large data are staged. Search/topics
produce no claims, relations, or clinical content; every result carries its
provenance (matched fields/terms, method, data source). Working tree is clean
after commit.
