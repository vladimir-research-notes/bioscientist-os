# Human review: Milestone 8 — Evaluation harness

## TL;DR
Added a gold-label **self-evaluation** of the pipeline: ingestion correctness,
BM25F search recall@k on labeled queries, dictionary entity precision/recall against
gold sets, claim-extraction sanity, evidence-table completeness, and provenance
coverage. Every rate is a `k/n` with its denominator and a 95% Wilson interval; small
N and the rule-based recall misses are surfaced, not hidden. New `evals` package
(`metrics` / `gold` / `harness`), committed gold labels under `data/fixtures/gold/`,
a `biosci eval` CLI, and `scripts/06_run_eval.py`. 28 new tests (223 total, 1 skipped
without `matplotlib`), all offline.

## What changed
- `src/bioscientist_os/evals/`: `metrics.py` (`Proportion` + Wilson interval +
  `z_for_confidence` + `f1_score`), `gold.py` (typed gold-label loaders +
  `GoldError`), `harness.py` (six evaluators + section dataclasses + `EvalReport` +
  `run_eval`); re-exported from `evals/__init__.py`.
- `data/fixtures/gold/`: `search_queries.json` (6 queries / 16 relevant pairs),
  `entity_labels.json` (6 abstracts / 24 gold entities), `README.md`.
- `src/bioscientist_os/cli.py`: `biosci eval` command; `info` status line and module
  docstring updated to Milestones 0–8.
- `scripts/06_run_eval.py`: thin wrapper (prints summary; writes `eval_report.json`).
- `tests/test_evals.py`: 28 tests.
- Docs + website: this note, the milestone note, the commit note; `EVALUATION.md`
  (method aligned to the implementation), `RESULTS.md` (Self-evaluation section +
  filled-in M4 entity P/R table + test count 223), `REPRODUCIBILITY.md` (eval
  determinism + `biosci eval`), `ROADMAP.md` (support-label gold scoring as future
  work); and `site/` (`evaluation` → Done, and `milestones`/`index`/`architecture`/
  `results` updated to M8 / 223 tests).

## Commands run
- `python3 -m pytest -q` → 223 passed, 1 skipped (offline).
- `ruff check src/bioscientist_os/evals/ src/bioscientist_os/cli.py scripts/06_run_eval.py tests/test_evals.py` → clean.
- `python3 scripts/01_ingest_fixtures.py --reset`, then `python3 scripts/06_run_eval.py`
  (wrote `results/processed/eval_report.json`); ran twice and diffed → identical JSON.
- `biosci eval --db results/raw/bioscientist.db --json` / `--recall-k 1 --recall-k 5`;
  empty-db error exit checked.

## Test status
223 passed, 1 skipped, offline. 28 of the tests are new (`tests/test_evals.py`); the
1 skip is the pre-existing M7 PNG-rendering test, skipped because `matplotlib` (the
optional `viz` extra) is not installed. No network is opened.

## Known limitations
- **Tiny, partly-synthetic corpus and gold labels.** N is small by construction, so
  Wilson intervals are wide (e.g. ingestion `40/40` → [0.912, 1.000]); the eval
  certifies *pipeline behavior*, not biological correctness or population performance.
- **Gold labels are single-annotator** and reflect the authors' reading of a narrow
  theme. They are committed and version-controlled, so the eval is reproducible, but
  they are not a multi-annotator standard.
- **Entity scoring is at distinct-entity-per-abstract granularity**, not per-span;
  span exactness is guaranteed by construction and tested in M4, not re-measured.
- **Several metrics are 1.0 by construction** (claim sanity, completeness, provenance
  coverage). They are regression floors, not achievements — a passing score there
  means "nothing regressed", not "the extraction is good".
- **The support/conflict/unknown label is not scored against a human verdict** — M8
  measures the evidence table's structural quality (completeness + provenance) only.
  Gold support annotations are listed as future work in `docs/ROADMAP.md`.

## Possible misleading artifacts
- **Precision = 1.000 is not "the recognizer is perfect."** The dictionary baseline
  cannot emit a false positive on these abstracts (it only matches known surfaces), so
  precision is high *by construction*; the informative number is recall (`22/24`),
  whose two misses (`IL-8` unmodeled, `p16INK4a-expressing` mis-tokenized) are the
  point. Do not read 1.000 as a quality ceiling.
- **`recall@5 = 16/16` does not mean retrieval is solved** — `recall@3 = 14/16` is the
  honest figure at the tighter cut-off, and both are on six small queries.
- **A 100% point estimate with a wide interval is weak evidence**, by design: the
  interval, not the point, conveys what the small N supports.
- `results/processed/eval_report.json` is a gitignored, regenerable artifact, not a
  committed source of truth; the canonical numbers live in `docs/RESULTS.md`.

## Human feedback
<!-- Human will fill this later. -->
