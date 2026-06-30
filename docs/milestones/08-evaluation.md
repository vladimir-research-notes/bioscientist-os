# Milestone 8 — Evaluation harness

## Summary

The workbench gains a **gold-label self-evaluation** of its own pipeline — not of
biological truth. It scores six things on the fixed, committed fixture corpus, each
reported as a count `k/n` with its **denominator** and a 95% **Wilson** confidence
interval: ingestion correctness, BM25F search recall@k on hand-labeled queries,
dictionary entity precision/recall against gold entity sets, claim-extraction sanity
(well-formed + span-traceable), evidence-table completeness, and provenance
coverage. No metric is reported without its denominator, heterogeneous tasks are
never collapsed into one headline number, and the rule-based recall *misses* are
surfaced rather than averaged away. New `biosci eval` CLI and
`scripts/06_run_eval.py`; the report is deterministic JSON.

## Deliverables

- **`src/bioscientist_os/evals/metrics.py`** — the statistics core: `Proportion`
  (a `k/n` with point estimate, Wilson interval, and JSON/text views), `wilson_interval`,
  `z_for_confidence` (via stdlib `statistics.NormalDist`, so any level works with no
  numerics dependency), and `f1_score`.
- **`src/bioscientist_os/evals/gold.py`** — typed, frozen loaders for the committed
  gold labels (`GoldQuery`, `GoldEntity`, `GoldEntityLabel`, `GoldLabels`,
  `load_gold`), with readable `GoldError`s on malformed files (the evaluation
  counterpart of `bioscientist_os.fixtures`).
- **`src/bioscientist_os/evals/harness.py`** — the six evaluators (`evaluate_ingestion`,
  `evaluate_search_recall`, `evaluate_entities`, `evaluate_claims`,
  `evaluate_evidence`), their frozen section-result dataclasses, the `EvalReport`
  container (text + JSON views), and the database-backed `run_eval(db)` (same
  not-a-database guard as the other subcommands).
- **Gold labels** under `data/fixtures/gold/`: `search_queries.json` (6 queries / 16
  relevant pairs), `entity_labels.json` (6 abstracts / 24 gold entities), and a
  `README.md` documenting authoring and the two deliberate recall misses.
- **CLI** (`cli.py`): a `biosci eval` command (`--db`, `--out`, `--confidence`,
  `--recall-k` repeatable, `--json`); `info` status and the module docstring updated
  to Milestones 0–8.
- **`scripts/06_run_eval.py`** — a thin, install-free wrapper that prints a
  denominator-first summary and writes `results/processed/eval_report.json`.
- **Tests**: `tests/test_evals.py` (28) — 223 total (1 skipped without `matplotlib`).

## Design notes / decisions

- **Denominator-first, never a bare percentage.** Every rate is a `Proportion`
  carrying its `k/n`. The Wilson interval (not Wald) is used because it stays in
  `[0, 1]` and is sensible at `k = 0` / `k = n` and small N — e.g. a perfect `40/40`
  ingestion score still reports a 95% lower bound of 0.912, which is the honest point.
- **Relevance judged independently of the ranker.** Gold query relevance was decided
  by reading abstracts, not by running BM25F, so recall is a fair measurement. Two
  relevant papers rank just outside the top 3 and are only recovered at k=5, giving
  an honest `recall@3 = 14/16 < 1.0`.
- **Recall misses are designed in, not hidden.** Entity precision is `22/22` (the
  dictionary baseline is high-precision by construction — no fuzzy matching, no false
  positives), and recall is `22/24`: `IL-8` has no fixture record, and
  `p16INK4a-expressing` is one hyphenated token so the `p16INK4a` surface does not
  match. Both are documented in the gold README, and the gold `modeled` flag is
  cross-checked against the live dictionary by a test.
- **Regression floors vs. achievements.** Claim sanity, completeness, and provenance
  are 1.0 *by construction* and are framed as floors (a span-round-trip check that
  reproduces every claim verbatim from its abstract, required-column population, full
  per-row provenance), not as quality wins.
- **Granularity stated honestly.** Entity scoring is at distinct-entity-per-abstract,
  matching what the recognizer emits; span exactness is guaranteed elsewhere (M4) and
  not re-measured. The support/conflict label is *not* scored against a human verdict
  (a documented future metric); M8 measures the table's structural quality only.
- **Deterministic and offline.** The evaluators are pure functions over the corpus,
  dictionary/extraction, and gold labels; every per-query/per-abstract/per-question
  detail is sorted before emission, so `eval_report.json` is byte-identical across
  runs.

## Validation

```bash
python3 -m pytest -q                                   # 223 passed, 1 skipped (offline)
python3 scripts/01_ingest_fixtures.py --reset          # -> results/raw/bioscientist.db
python3 scripts/06_run_eval.py                         # -> results/processed/eval_report.json
biosci eval --db results/raw/bioscientist.db --json
biosci eval --db results/raw/bioscientist.db --recall-k 1 --recall-k 5
ruff check src/bioscientist_os/evals/ src/bioscientist_os/cli.py \
    scripts/06_run_eval.py tests/test_evals.py         # clean
```

Measured on the committed fixtures and gold labels (these are *pipeline* numbers, on
a tiny, partly-synthetic corpus — not biological truth):

| Metric | Value (95% Wilson CI) | Denominator |
|--------|-----------------------|-------------|
| ingestion correctness | 1.000 [0.912, 1.000] | 40 / 40 fixture records |
| search recall@3 (micro) | 0.875 [0.640, 0.965] | 14 / 16 relevant pairs |
| search recall@5 (micro) | 1.000 [0.806, 1.000] | 16 / 16 relevant pairs |
| entity precision | 1.000 [0.851, 1.000] | 22 / 22 recognized |
| entity recall | 0.917 [0.742, 0.977] | 22 / 24 gold entities |
| entity F1 | 0.957 | TP=22, FP=0, FN=2 |
| claim sanity | 1.000 [0.916, 1.000] | 42 / 42 claims |
| evidence completeness | 1.000 [0.947, 1.000] | 68 / 68 rows |
| provenance coverage | 1.000 [0.947, 1.000] | 68 / 68 rows |

The 28 evaluation tests pin: the Wilson math and its edge cases (`n=0`, `k=0`,
`k=n`, bad counts), the `Proportion` denominator/None-point behavior, the gold
loader and its `modeled`-flag cross-check against the live dictionary, each
evaluator against its committed denominators (including the missing-row ingestion
case, the recorded relevant ranks, and the two documented entity misses), `run_eval`
determinism and the not-a-database guard, that a higher confidence widens the
interval, and the `biosci eval` CLI (text, JSON, `--out`, bad-confidence and
empty-db exits). All tests are offline (no network, no paid API, no GPU).

## Status

**Complete.** Next: **Milestone 9 — End-to-end research memo generation** (a
structured memo from the corpus: research question, key papers, extracted claims,
evidence table, database links, conflicts/uncertainties, suggested next experiments
**as hypotheses only**, limitations, and exact provenance — no medical advice).
