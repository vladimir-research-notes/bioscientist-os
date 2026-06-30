# Commit note: Milestone 8 — Add evaluation harness with gold labels

## Intent
Give the workbench an honest, reproducible self-evaluation of its **own pipeline**
(not of biological truth), built on the project's disciplines: every rate is a count
`k/n` that carries its denominator and a 95% Wilson interval, heterogeneous tasks are
never collapsed into one headline number, and the rule-based baseline's recall
*misses* are surfaced rather than averaged away.

## What the commit contains
- `src/bioscientist_os/evals/metrics.py`: `Proportion` (point estimate + Wilson
  interval + JSON/text views), `wilson_interval`, `z_for_confidence` (stdlib
  `statistics.NormalDist`, so any level works with no numerics dependency), `f1_score`.
- `src/bioscientist_os/evals/gold.py`: typed, frozen loaders for the committed gold
  labels (`GoldQuery`, `GoldEntity`, `GoldEntityLabel`, `GoldLabels`, `load_gold`)
  with readable `GoldError`s — the evaluation counterpart of `bioscientist_os.fixtures`.
- `src/bioscientist_os/evals/harness.py`: the six evaluators (`evaluate_ingestion`,
  `evaluate_search_recall`, `evaluate_entities`, `evaluate_claims`,
  `evaluate_evidence`), their frozen section dataclasses, the `EvalReport` container,
  and the database-backed `run_eval(db)` (same not-a-database guard as the other
  subcommands). Pure, deterministic, sorted-before-emit.
- `src/bioscientist_os/evals/__init__.py`: re-export the M8 surface.
- `data/fixtures/gold/`: `search_queries.json`, `entity_labels.json`, and `README.md`
  (committed, version-controlled gold labels; documents the two deliberate misses).
- `src/bioscientist_os/cli.py`: `biosci eval` command (`--db`, `--out`,
  `--confidence`, `--recall-k`, `--json`); `info` and the module docstring → M0–8.
- `scripts/06_run_eval.py`: thin, install-free wrapper.
- `tests/test_evals.py` (28): the Wilson math + edge cases, the `Proportion`
  behavior, the gold loader with its `modeled`-flag cross-check, each evaluator
  against its committed denominators (the missing-row ingestion case, the recorded
  relevant ranks, the two documented entity misses), `run_eval` determinism and the
  not-a-database guard, confidence widening the interval, and the `biosci eval` CLI.
  223 total, 1 skipped without `matplotlib`.
- Docs + website: milestone/commit/review notes; `EVALUATION.md` (method aligned to
  the implementation), `RESULTS.md` (Self-evaluation section, filled-in M4 entity P/R
  table, test count 223), `REPRODUCIBILITY.md` (eval determinism + `biosci eval`),
  `ROADMAP.md` (support-label gold scoring as future work); `site/`
  (`evaluation` → Done; `milestones`/`index`/`architecture`/`results` updated to M8 →
  Done and 223 tests).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The new code adds no third-party
dependency (the Wilson interval uses the stdlib `statistics.NormalDist`). The gold
labels are tiny committed JSON, clearly marked as the authors' single-annotator
judgment on a synthetic theme. The only generated artifact is
`results/processed/eval_report.json` (gitignored, regenerable, byte-identical across
runs) and is not staged. No secrets, caches, virtualenvs, weights, or large data are
staged. The evaluation measures the **pipeline**, never biological truth: its
numbers are reported with denominators and Wilson intervals, the recall misses are
documented, and the metrics that are 1.0 by construction are framed as regression
floors — so nothing here reads as a clinical or biological claim (see
`docs/SAFETY.md`). `ruff check` is clean on the new/changed files; the pre-existing
E501 in `tests/test_repo_contract.py` is unrelated and left untouched. Working tree
is clean after commit.
