# Commit note: Milestone 9 — Add end-to-end research memo generator

## Intent
Give the workbench its narrative capstone: a structured research memo per research
question, assembled by **composing** the existing pipeline layers (no new, unaudited
computation) and obeying the project's disciplines — the four epistemic levels are
tagged and never collapsed, every evidence row carries full provenance, suggested next
experiments are emitted **only** as explicitly unsupported hypotheses, and the memo is
framed throughout as a research-assistance artifact, **not** medical advice.

## What the commit contains
- `src/bioscientist_os/evidence/memo.py`: the memo engine — `MemoReport` (deterministic
  `to_dict()` JSON + GitHub-flavored `to_markdown()` views), `build_memo_report(...)`
  and the database-backed `load_memo(db, ...)` (same not-a-database / unknown-id guards
  as the other subcommands), the section containers `KeyPaper` / `EntityLinks` /
  `DirectionalDisagreement` / `Hypothesis`, a candidate cross-paper directional-
  disagreement detector (differing relation verbs on a `{subject, object}` entity pair
  across papers), and a mechanical unsupported-hypothesis generator. Pure,
  deterministic, sorted-before-emit; reuses M3 BM25F, M4 extraction, and the M5
  evidence table (whose counts/links it reconciles with exactly).
- `src/bioscientist_os/evidence/__init__.py`: re-export the M9 surface alongside M4/M5.
- `src/bioscientist_os/cli.py`: `biosci memo` command (`--question`, `--question-id`,
  `--out`, `--json`, `--min-confidence`, `--limit`, `--max-papers`, `--max-hypotheses`);
  default output is the Markdown memo, `--json` emits the structured report; `info` and
  the module docstring → Milestones 0–9.
- `scripts/07_generate_memo.py`: thin, install-free wrapper writing one
  `memo_<question_id>.md` per stored question plus `memo.md` and `memos.json`.
- `tests/test_memo.py` (20): the nine required sections + header; the four epistemic-
  level tags + legend; the no-medical-advice framing; every hypothesis
  `status="unsupported"` and question-framed under an UNSUPPORTED/UNTESTED header; the
  conflict rows matching the `conflict` label; key papers limited to contributors and
  ranked, with their BM25F signal; the aggregate + per-entity database links (IL-6
  case); reconciliation with the M5 table and 100% provenance coverage; filter
  passthrough; determinism of both views; `load_memo` equalling the in-memory build and
  an ad-hoc free-text question; and the `biosci memo` CLI (Markdown/JSON/`--out`,
  requires-a-question exit 2, unknown-id exit 1, empty-db exit 1). 243 total, 1 skipped
  without `matplotlib`.
- Docs + website: milestone/commit/review notes (`docs/milestones/09-research-memo.md`,
  `docs/commits/09-research-memo.md`, `docs/review_notes/09-research-memo-human-review.md`);
  `RESULTS.md` (Research-memo section, status row, test count → 243); `REPRODUCIBILITY.md`
  (the `07_generate_memo.py` step and the `biosci memo` example); `site/` (new
  `memo.html` page, the nav link added across all pages, `milestones` M9 → Done with a
  delivered section, `results` updated to M9 and 243 tests).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The memo adds no third-party
dependency — it composes layers that already exist, so it cannot disagree with the
evidence table (a test asserts the reconciliation). The only generated artifacts are
under `results/processed/` (`memo*.md`, `memos.json` — gitignored, regenerable,
byte-identical across runs) and are not staged. No secrets, caches, virtualenvs,
weights, or large data are staged. The output is a research-assistance artifact, never
medical advice: it opens and closes with the non-clinical statement, the support label
is a heuristic *textual* signal, database links are *inferred relations*, and suggested
experiments are *unsupported* hypotheses framed as research questions — never
recommendations, protocols, or clinical guidance (see `docs/SAFETY.md`). `ruff check`
is clean on the new/changed files. Working tree is clean after commit.
