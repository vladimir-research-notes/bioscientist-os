# Commit note: Milestone 7 — Add workbench visualizations

## Intent
Give the workbench five figures — a literature timeline, a topic-cluster summary, a
claim/evidence matrix, an entity/database-link graph, and a support-vs-conflict
table — without breaking the project's discipline: keep the **figure data** (the
numbers a figure draws) separate from the **rendering** (the PNG), so the data stays
pure, deterministic, provenance-carrying, and testable on the light core path while
`matplotlib` remains an optional extra.

## What the commit contains
- `src/bioscientist_os/visualization/model.py`: frozen, `matplotlib`-free,
  JSON-serializable figure-data dataclasses (`TimelineSeries`, `ClusterSummary`,
  `EvidenceMatrix`, `LinkGraph`, `SupportConflictTable`), the `VisualizationReport`
  container, and `VisualizationError`. Each carries a `method`, a `data_source`, and
  denominators; the matrix/table captions carry the "not a biological verdict" framing.
- `src/bioscientist_os/visualization/build.py`: the builders, the
  `build_visualization_report` assembler, and the database-backed
  `load_visualizations(db)`. Re-presents the M3 topic grouping, M4 extraction, and M5
  evidence tables; sorts everything before emitting, so the data is deterministic.
- `src/bioscientist_os/visualization/figures.py`: the *optional* `matplotlib`
  renderer (`matplotlib_available`, per-figure `render_*` with the headless `Agg`
  backend and a seeded `networkx` layout, `render_figures`) and
  `write_visualizations` (always writes `visualizations.json`; renders PNGs only when
  `matplotlib` is present, reported via `VisualizationArtifacts`).
- `src/bioscientist_os/visualization/__init__.py`: re-export the M7 surface.
- `src/bioscientist_os/cli.py`: `biosci figures` command (`--db`, `--out-dir`,
  `--question` / `--question-id`, `--threshold`, `--no-render`, `--json`); `info` and
  the module docstring updated to Milestones 0–7.
- `scripts/05_generate_visualizations.py`: thin, install-free wrapper.
- `tests/test_visualizations.py` (18): figure-data builders (timeline/cluster/matrix/
  graph/table), the highest-confidence cell rule, link-graph consistency, support-count
  agreement with the M5 tables, JSON determinism, the safety framing,
  `write_visualizations` (JSON always; render flag = `matplotlib` availability), the
  `VisualizationError` guard, and the CLI. 195 total, 1 skipped without `matplotlib`.
- Docs + website: milestone/commit/review notes; `RESULTS.md` (Figures section, test
  count), `REPRODUCIBILITY.md` (determinism + `biosci figures`); `site/`
  (`visualizations` → Done; `milestones`/`index`/`architecture`/`results` updated to
  M7 → Done and 195 tests).

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. `matplotlib` is an optional extra
(`.[viz]`); with it absent the figure data is still produced and only the rendering
test is skipped, so the default path needs no new dependency. The only generated
artifacts are under `results/figures/` (gitignored, regenerable) and are not staged.
No secrets, caches, virtualenvs, weights, or large data are staged. The figures
re-present existing reports rather than computing anything new, so the matrix/table
support counts equal the M5 evidence tables' counts and the link-graph database links
mirror the M5 link-assembly rule — both asserted by tests. The matrix/table support
signal is a heuristic *textual* signal and the link-graph database edges are *inferred
relations* — neither is a biological or clinical assertion, and every figure carries
its `data_source` provenance. `ruff check` is clean on the new/changed files; the one
pre-existing E501 in `tests/test_repo_contract.py` is unrelated and left untouched.
Working tree is clean after commit.
