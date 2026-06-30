# Human review: Milestone 9 — End-to-end research memo generation

## TL;DR
A new `biosci memo` command and `src/bioscientist_os/evidence/memo.py` assemble a
structured research memo per research question by composing the existing pipeline
(M3 BM25F key papers, the M5 evidence table, database links, conflicts/uncertainties)
and a mechanical unsupported-hypothesis generator. The four epistemic levels are tagged
and kept separate, every evidence row carries full provenance, and suggested next
experiments are emitted only as explicitly unsupported, UNTESTED hypotheses. No medical
advice. 20 new tests; 243 passed, 1 skipped (offline).

## What changed
- `src/bioscientist_os/evidence/memo.py` — `MemoReport` (Markdown + JSON views),
  `build_memo_report` / `load_memo`, the `KeyPaper` / `EntityLinks` /
  `DirectionalDisagreement` / `Hypothesis` containers, the candidate directional-
  disagreement detector, and the unsupported-hypothesis generator.
- `src/bioscientist_os/evidence/__init__.py` — re-export the M9 surface.
- `src/bioscientist_os/cli.py` — the `biosci memo` command; `info` + docstring → M0–9.
- `scripts/07_generate_memo.py` — thin wrapper writing `memo_<qid>.md`, `memo.md`,
  `memos.json` under `results/processed/` (gitignored).
- `tests/test_memo.py` — 20 tests.
- Docs/website: this note, the milestone and commit notes, `RESULTS.md`,
  `REPRODUCIBILITY.md`, and `site/` (new `memo.html`, nav link added to every page,
  `milestones`/`results` updated to M9 → Done and 243 tests).

## Commands run
```bash
python3 -m pytest -q                                   # 243 passed, 1 skipped (offline)
python3 scripts/01_ingest_fixtures.py --reset
python3 scripts/07_generate_memo.py
biosci memo --db results/raw/bioscientist.db \
  --question "What evidence links cellular senescence to chronic inflammation?"
biosci memo --db results/raw/bioscientist.db --question-id rq-autophagy-senescence --json
ruff check src/bioscientist_os/evidence/memo.py src/bioscientist_os/cli.py \
    scripts/07_generate_memo.py tests/test_memo.py     # clean
```

## Test status
243 passed, 1 skipped (the figure-rendering test, skipped because `matplotlib` is not
installed). `ruff check` clean on the new/changed files. All tests offline; no network,
paid API, or GPU.

## Known limitations
- The candidate directional-disagreement detector flags differing relation *verbs* on
  an entity pair; some differing verbs are not truly contradictory, so it is
  deliberately recall-oriented and framed as a *candidate* for human review, not a
  verdict. It only inspects claims with extracted relation triples.
- "Key papers" are the papers that contributed evidence rows, ranked by contribution;
  a relevant paper from which the rule-based extractor produced no claim will not
  appear as a key paper (it is surfaced instead in the retrieval recall gap).
- Hypotheses and the support/conflict label are not scored against a human verdict
  (future work, see `docs/ROADMAP.md`); the memo is built on a tiny, partly-synthetic
  corpus, so its counts illustrate behavior, not biological truth.

## Possible misleading artifacts
- The memo reads like a finished research summary. It is not: the support label is a
  heuristic *textual* signal, the database links are *inferred relations*, and the
  "suggested next experiments" are *unsupported* hypotheses for a human to evaluate.
  These are labeled inline and in the opening/closing non-clinical statement, but a
  reader skimming only section 4 could over-trust the rows.
- A "candidate directional disagreement" names a real, designed conflict in the
  fixtures (autophagy 006 vs 007); a reviewer should confirm the framing makes clear it
  is a candidate to verify, not an asserted biological conflict.
- All numbers are on the committed synthetic/derived fixtures and must not be cited as
  performance or biological claims.

## Human feedback
<!-- Human will fill this later. -->
