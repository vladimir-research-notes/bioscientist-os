# Human review: Milestone 7 — Visualizations

## TL;DR
Added five workbench figures — a literature timeline, a topic-cluster summary, a
claim/evidence matrix, an entity/database-link graph, and a support-vs-conflict
table — each split into **inspectable data** (pure, deterministic, provenance-
carrying, always written to `results/figures/visualizations.json`) and **optional
`matplotlib` rendering** (PNGs only when the `viz` extra is installed). The figures
re-present the M3/M4/M5 reports rather than recomputing anything, so their numbers
reconcile with the earlier milestones. New `biosci figures` CLI and
`scripts/05_generate_visualizations.py`. 18 new tests (195 total, 1 skipped without
`matplotlib`), all offline.

## What changed
- `src/bioscientist_os/visualization/`: `model.py` (figure-data dataclasses +
  `VisualizationReport` + `VisualizationError`), `build.py` (builders +
  `build_visualization_report` + `load_visualizations`), `figures.py` (optional
  `matplotlib` renderer + `write_visualizations` + `matplotlib_available`);
  re-exported from `visualization/__init__.py`.
- `src/bioscientist_os/cli.py`: `biosci figures` command; `info` status line and the
  module docstring updated to Milestones 0–7.
- `scripts/05_generate_visualizations.py`: thin wrapper (data always; PNGs optional;
  `--no-render`).
- `tests/test_visualizations.py`: figure-data tests (always run) + the PNG-render
  test (skipped without `matplotlib`) + CLI tests.
- Docs + website: this note, the milestone note, the commit note; `RESULTS.md`
  (Figures section + test count), `REPRODUCIBILITY.md` (determinism + `biosci figures`);
  and `site/` (`visualizations` → Done, and `milestones`/`index`/`architecture`/`results`
  updated to M7 / 195 tests).

## Commands run
- `python3 -m pytest -q` → 195 passed, 1 skipped (offline).
- `ruff check src/bioscientist_os/visualization/ src/bioscientist_os/cli.py scripts/05_generate_visualizations.py tests/test_visualizations.py` → clean.
- `python3 scripts/01_ingest_fixtures.py --reset`, then
  `python3 scripts/05_generate_visualizations.py` (matplotlib absent → JSON written,
  PNGs skipped), `--no-render`, and `biosci figures --json` / `--question-id ...`.

## Test status
195 passed, 1 skipped, offline. 18 of the tests are new
(`tests/test_visualizations.py`); the 1 skip is the PNG-rendering test, skipped here
because `matplotlib` (the optional `viz` extra) is not installed. No network is
opened.

## Known limitations
- `matplotlib` is **not installed in this environment**, so the PNG-rendering path
  (`render_*` in `figures.py`) was exercised only for its absence-guard
  (`VisualizationError`), not for actual image output. The renderers are written
  defensively (headless `Agg` backend, seeded layout) but the produced PNGs have not
  been visually inspected here; the figure *data* is fully tested.
- Only the figure **data** is byte-deterministic. PNG bytes can vary across
  `matplotlib` versions/fonts; the network-graph layout is seeded for visual
  stability, not byte-stability.
- Figures summarize a tiny, partly-synthetic, theme-focused corpus — they are
  descriptive, not field maps. Counts are figure *structure*, not a quality metric.
- The evidence matrix defaults to one (the first stored) research question; the other
  questions appear only via the support-vs-conflict table unless `--question` is passed.
- The link graph includes only entities that appear in ≥1 extracted claim; isolated
  dictionary entities are intentionally omitted.

## Possible misleading artifacts
- The matrix/table **support/conflict/unknown** signal is a heuristic *textual* signal
  (`rule:support-cues`) about one sentence's phrasing — **not** a biological or
  clinical verdict, and it does not detect cross-paper directional conflict (e.g.
  paper-006 vs paper-007 on autophagy↔senescence both read as support per row).
- The link graph's **database edges** are *inferred relations* (assembled by combining
  records), not asserted biological facts; co-occurrence edges only mean two entities
  shared a claim sentence.
- A matrix cell of `none` means "no claim links this paper to this entity" (a coverage
  gap), which is different from `unknown` ("a claim exists but its phrasing is
  neutral") — do not read `none` as evidence of absence.
- `results/figures/*` are gitignored, regenerable artifacts, not committed and not a
  source of truth.

## Human feedback
<!-- Human will fill this later. -->
