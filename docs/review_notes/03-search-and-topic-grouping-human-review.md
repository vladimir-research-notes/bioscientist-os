# Human review: Milestone 3 — Search and topic grouping

## TL;DR
Added CPU-only, offline search (BM25F with a full per-term/per-field score
explanation, plus an optional TF-IDF cosine mode) and transparent single-link
topic grouping over the ingested corpus, with `biosci search` / `biosci topics`
CLI commands and a `scripts/02_build_index.py` wrapper. 28 new tests (95 total),
all offline. No claims are produced; results are rankings/groupings of
observed-metadata papers.

## What changed
- `src/bioscientist_os/search/`: `tokenize.py` (tokenizer + stop list + idf
  helpers), `index.py` (`SearchIndex`: BM25F + TF-IDF cosine, `load_index`),
  `topics.py` (`group_topics`, single-link cosine clustering via networkx),
  `model.py` (result dataclasses with `to_dict`), and re-exporting `__init__.py`.
- `src/bioscientist_os/cli.py`: `search` and `topics` subcommands (`--limit`,
  `--method`, `--explain`, `--threshold`, `--top-terms`, `--json`); `info` status
  line updated to Milestones 0–3.
- `scripts/02_build_index.py`: install-free wrapper; writes
  `results/processed/search_index.json` (gitignored).
- `tests/test_search.py`: tokenizer, BM25F scoring/explanation/determinism,
  field weighting, labeled queries, TF-IDF cosine, topic partition/monotonicity,
  and the CLI.
- Docs + website: this note, the milestone note, the commit note, `RESULTS.md`,
  `REPRODUCIBILITY.md`, `ARCHITECTURE.md`, and `site/` (new `search.html`, nav
  link on every page, and `milestones`/`index`/`architecture`/`results` updated).

## Commands run
- `python3 -m pytest -q` → 95 passed (offline).
- `ruff check` on the new/changed files → clean.
- `python3 scripts/01_ingest_fixtures.py --reset`, then
  `python3 scripts/02_build_index.py --query "..." --query "..."`.
- `biosci search "IL-6 SASP senescence" --db ... --explain`, `biosci topics --db ...`.

## Test status
95 passed, 0 failed, offline. 28 of the tests are new (`tests/test_search.py`).

## Known limitations
- The tokenizer does no stemming or synonym/identifier normalization, so `IL-6`
  and `IL6` are different tokens (unification is Milestone 4 entity linking).
- Topic grouping is single-link clustering at a cosine threshold: it can chain
  loosely-related papers and cannot place one paper in two themes. The threshold
  (`0.15`) was chosen on these fixtures; it is exposed and reported, not hidden.
- The index is recomputed in memory per run (no persisted inverted index) —
  appropriate for small corpora, a scaling limitation at larger ones.
- Search quality numbers are on a tiny, partly-synthetic corpus and are
  illustrative; the rigorous evaluation (denominators, intervals) is Milestone 8.

## Possible misleading artifacts
- The topic *labels* are the most distinctive terms of a group; they describe the
  group, they are **not** asserted topics of the field. A reader should not read
  `topic-04: senolytic, …` as a claim.
- `hit@k` on 8 single-target labeled queries is a sanity check, not a recall
  benchmark; do not generalize it.
- `search_index.json` under `results/processed/` is a regenerable inspection
  artifact, not committed and not a source of truth.

## Human feedback
<!-- Human will fill this later. -->
