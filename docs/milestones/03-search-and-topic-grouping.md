# Milestone 3 — Search and topic grouping

## Summary

The ingested corpus is now searchable and groupable, entirely on CPU and offline.
`bioscientist-os` gains a field-aware in-memory `SearchIndex` with a transparent
**BM25F** lexical scorer (and an optional TF-IDF cosine mode), **single-link
cosine topic grouping**, the `biosci search` / `biosci topics` CLI commands, and a
thin `scripts/02_build_index.py` wrapper. Every search hit carries a per-term,
per-field score breakdown that reconstructs the score exactly; every topic group
carries the distinctive terms that label it. No claims or relations are produced —
results are rankings and groupings of *observed-metadata* papers.

## Deliverables

- **`src/bioscientist_os/search/tokenize.py`** — the transparent tokenizer
  (lowercase; alphanumeric tokens with internal hyphens kept, so `IL-6`,
  `p16INK4a`, `ATG7-dependent` survive as single tokens), a small documented stop
  list used only for TF-IDF/topics, and the BM25 / TF-IDF inverse-document-frequency
  helpers. No stemming or synonym expansion (that would hide which literal term
  matched; identifier normalization is Milestone 4's job).
- **`src/bioscientist_os/search/index.py`** — `SearchIndex`:
  - three weighted fields (`title` 3.0 / `keywords` 2.0 / `abstract` 1.0) with
    BM25F (`k1=1.5`, `b=0.75`); `search()` returns hits sorted by score then
    `paper_id`, each with a `TermMatch` per query term (idf, per-field tf,
    weighted tf, additive contribution) such that `score == Σ contributions`;
  - smoothed, L2-normalized TF-IDF vectors + cosine (`tfidf_vectors`, `cosine`)
    and an optional `tfidf_search()`;
  - `corpus_stats()`, and `load_index(db)` mirroring the `biosci stats`
    not-a-database guard.
- **`src/bioscientist_os/search/topics.py`** — `group_topics()`: connected
  components of a TF-IDF cosine graph at a threshold (default `0.15`), labeled by
  top-TF-IDF-mass terms. Deterministic and monotone in the threshold.
- **`src/bioscientist_os/search/model.py`** — frozen result dataclasses
  (`TermMatch`, `SearchHit`, `SearchResponse`, `TopicGroup`, `TopicReport`) with
  `to_dict()` for `--json`.
- **CLI** (`cli.py`): `biosci search "<query>" --db <path> [--limit N]
  [--method bm25|tfidf] [--explain] [--json]` and `biosci topics --db <path>
  [--threshold T] [--top-terms K] [--json]`. Both surface method, parameters,
  data source, and the non-clinical stance.
- **`scripts/02_build_index.py`** — install-free wrapper: prints corpus stats and
  the topic grouping, runs demo `--query`s, and writes
  `results/processed/search_index.json` (gitignored, regenerable).
- **Tests**: `tests/test_search.py` (28) — 95 total, all offline.

## Design notes / decisions

- **BM25F, not a black box.** The multi-field BM25 variant lets a title/keyword
  match outweigh an abstract-only match, and the per-term contribution is computed
  explicitly so the explanation *is* the score (`score == Σ contributions`, a
  tested invariant). This is the milestone's "which terms matched, which fields,
  scores" requirement made literal.
- **Hyphen-preserving tokenizer, no normalization.** Keeping `IL-6` and `il-6`
  identical but distinct from `il6` is an honest limitation: search shows the
  literal surface match; unifying `IL-6`/`IL6`/UniProt ids is entity linking
  (M4), deliberately *not* done here so search stays auditable.
- **Single-link clustering, named for what it is.** Topic grouping is connected
  components of a cosine-threshold graph — a transparent baseline, not a topic
  model. It is deterministic and monotone in the threshold (raising it never
  merges groups). Its weaknesses are stated: single linkage can chain, and it
  cannot place a paper in two themes. The threshold is exposed and reported.
- **In-memory index.** For the small corpora this workbench targets, the index is
  recomputed from SQLite per run rather than persisted — a pure, deterministic
  function of the database. The O(papers × query-terms) cost is negligible here
  and called out as a scaling limitation rather than hidden. The JSON summary is
  an inspection artifact, not a persisted inverted index.
- **No epistemic upgrade.** Search/topics do not enter the four-level claim
  vocabulary; their results are plain dataclasses (like `IngestReport`), but still
  provenance-bearing (matched fields/terms, method, data source on every result).

## Validation

```bash
python3 -m pytest -q                                  # 95 passed (offline)
python3 scripts/01_ingest_fixtures.py --reset         # -> results/raw/bioscientist.db
python3 scripts/02_build_index.py \
    --query "cellular senescence inflammation" \
    --query "autophagy mTOR rapamycin"                # corpus stats + topics + demo hits
biosci search "IL-6 SASP senescence" --db results/raw/bioscientist.db --explain
biosci topics --db results/raw/bioscientist.db
ruff check src/bioscientist_os/search src/bioscientist_os/cli.py \
           scripts/02_build_index.py tests/test_search.py        # clean
```

Measured on the committed fixtures (18 papers, 436-term vocabulary): topic
grouping at threshold `0.15` yields 10 groups (4 multi-paper, 6 singletons) —
SASP/secretion, senescence markers, autophagy/mTOR/longevity, and senolytics are
the multi-paper groups. On 8 single-target hand-labeled queries the expected paper
is rank 1 in 7/8 and within the top 3 in 8/8 (illustrative on a tiny synthetic
corpus; the rigorous evaluation with denominators and intervals is Milestone 8).
All offline; no network, no paid API, no GPU.

## Status

**Complete.** Next: **Milestone 4 — Entity and claim extraction baseline** (a
transparent, non-LLM dictionary entity recognizer plus claim-sentence extraction
with confidence and provenance on every extraction).
