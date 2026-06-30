# Milestone 7 — Visualizations

## Summary

The workbench gains **five figures** that summarize the corpus and the evidence,
each split into **inspectable data** and **optional rendering**. The figure *data*
is a pure, deterministic, provenance-carrying re-presentation of the workbench's own
reports (the M3 topic grouping, the M4 extraction, the M5 evidence tables) — it adds
no new, unaudited computation — and is always written to
`results/figures/visualizations.json`. PNG rendering uses `matplotlib`, an
**optional extra**: when it is absent the PNGs (and the figure-rendering test) are
skipped, but the JSON is still produced, so the core path stays light and the chain
stays inspectable.

The five figures match `docs/PLAN.md`: a literature timeline, a topic-cluster
summary, a claim/evidence matrix, an entity/database-link graph, and a
support-vs-conflict table.

## Deliverables

- **`src/bioscientist_os/visualization/model.py`** — frozen, `matplotlib`-free,
  JSON-serializable figure-data dataclasses, each carrying a `method`, a
  `data_source`, and explicit denominators: `TimelineSeries`, `ClusterSummary`,
  `EvidenceMatrix`, `LinkGraph`, `SupportConflictTable`, plus the `VisualizationReport`
  container and `VisualizationError`. The matrix and table captions carry the "not a
  biological verdict" framing.
- **`src/bioscientist_os/visualization/build.py`** — the builders
  (`build_timeline`, `build_cluster_summary`, `build_evidence_matrix`,
  `build_link_graph`, `build_support_conflict_table`), the `build_visualization_report`
  assembler, and the database-backed `load_visualizations(db)` (same
  not-a-database guard as the other subcommands). Everything is sorted before it is
  emitted, so the JSON is deterministic.
- **`src/bioscientist_os/visualization/figures.py`** — the *optional* `matplotlib`
  renderer: `matplotlib_available()`, per-figure `render_*` functions (headless `Agg`
  backend; the link graph uses a seeded `networkx` spring layout), `render_figures`,
  and `write_visualizations` (writes the data JSON unconditionally; renders PNGs only
  when `matplotlib` is present, reporting honestly via `VisualizationArtifacts`).
- **CLI** (`cli.py`): a `biosci figures` command (`--db`, `--out-dir`, `--question` /
  `--question-id`, `--threshold`, `--no-render`, `--json`); `info` status and the
  module docstring updated to Milestones 0–7.
- **`scripts/05_generate_visualizations.py`** — a thin, install-free wrapper that
  prints a per-figure summary and writes the artifacts.
- **Tests**: `tests/test_visualizations.py` (18) — 195 total (1 skipped without
  `matplotlib`).

## Design notes / decisions

- **Data first, pixels second.** The artifact a reviewer audits is
  `visualizations.json`, not a PNG. Separating the figure *data* (pure, tested,
  deterministic, provenance-carrying) from the *rendering* (optional, skipped when
  `matplotlib` is absent) is what keeps the figures inside the project's provenance
  discipline and the core test path light — and it is why this milestone is genuinely
  runnable and testable offline even with `matplotlib` uninstalled.
- **Figures re-present, they do not recompute.** Each builder consumes an existing
  report (topics, extraction, evidence table) rather than introducing a parallel
  computation. The support-vs-conflict counts therefore equal the M5 tables' counts
  exactly (asserted by a test), and the link graph's database links mirror the M5
  link-assembly rule (UniProt/HGNC xrefs + Open Targets associations matched by HGNC
  gene), so the two never drift.
- **Honest cell vocabulary.** The evidence-matrix cell is the *highest-confidence*
  support label of the rows linking a paper to a question entity (ties → smallest
  `claim_id`). `none` (no claim links them) is kept distinct from `unknown` (a claim
  exists but its phrasing neither affirms nor negates), so coverage gaps are visible
  rather than silently read as "unknown".
- **Determinism where it can be guaranteed.** Series, nodes, and edges are sorted, so
  `visualizations.json` is byte-identical across runs. PNG bytes can vary across
  `matplotlib` versions/fonts (documented, like the raw `.db` caveat); the graph
  layout is seeded for visual stability.
- **Epistemic framing travels with the figure.** The matrix/table support signal is
  a heuristic *textual* signal and the link-graph database edges are *inferred
  relations*; both captions say so, and the CLI/script footers repeat it — neither is
  a biological or clinical verdict (see `docs/SAFETY.md`).

## Validation

```bash
python3 -m pytest -q                                   # 195 passed, 1 skipped (offline)
python3 scripts/01_ingest_fixtures.py --reset          # -> results/raw/bioscientist.db
python3 scripts/05_generate_visualizations.py          # -> results/figures/visualizations.json (+PNGs if matplotlib)
python3 scripts/05_generate_visualizations.py --no-render
biosci figures --db results/raw/bioscientist.db --json
biosci figures --db results/raw/bioscientist.db --question-id rq-senescence-inflammation
ruff check src/bioscientist_os/visualization/ src/bioscientist_os/cli.py \
    scripts/05_generate_visualizations.py tests/test_visualizations.py   # clean
```

Measured on the committed fixtures (figure-data **counts and structure**, not a
quality metric):

| Figure | On the fixtures |
|--------|-----------------|
| timeline | 18 papers across 17 years (0 undated) |
| topic clusters | 10 groups (6 singleton) at threshold 0.15 |
| evidence matrix (`rq-autophagy-senescence`) | 14 papers × 5 entities (29 claim rows): 18 support / 3 conflict / 1 unknown / 48 none |
| link graph | 53 nodes (24 entity, 29 database); 80 edges (51 co-occurrence, 20 xref, 9 association) |
| support-vs-conflict | 3 questions: 36 support / 13 conflict / 19 unknown (68 rows) |

The 18 visualization tests pin: timeline counts (every paper accounted for, sorted
years), cluster-summary agreement with `group_topics` (sizes sum to the corpus,
largest first), the matrix shape/vocabulary and the highest-confidence cell rule
(recomputed independently), link-graph node/edge consistency (every endpoint a real
node, co-occurrence undirected and ordered, recorded degree = incident-edge count,
the IL-6 entity's UniProt/HGNC/Open Targets links present), support-count agreement
with the M5 evidence tables, JSON determinism and serializability, the safety
framing, `write_visualizations` always writing the JSON with the render flag matching
`matplotlib` availability, the `VisualizationError` guard when `matplotlib` is absent,
and the `biosci figures` CLI (JSON, artifact writing, `--no-render`, error exit). The
PNG-rendering test is skipped when `matplotlib` is not installed; all tests are
offline (no network, no paid API, no GPU).

## Status

**Complete.** Next: **Milestone 8 — Evaluation harness** (ingestion correctness,
search recall on hand-labeled queries, entity-extraction precision/recall on tiny
gold labels, claim-extraction sanity checks, evidence-table completeness, and
provenance coverage, reported with clear denominators and Wilson intervals).
