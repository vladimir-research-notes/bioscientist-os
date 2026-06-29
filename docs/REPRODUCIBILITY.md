# Reproducibility

## TL;DR

Everything in the default path is reproducible offline on a CPU. Create a venv,
install dev extras, run the environment check, run the tests. As milestones land,
the same fixtures deterministically regenerate the database, search results,
claims, evidence tables, figures, memo, and evaluation report.

## Short explanation

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python3 scripts/00_check_environment.py     # offline environment report
python3 -m pytest -q                         # offline test suite
```

No network, no GPU, no paid API are required for any of the above.

## Longer explanation

### Determinism

Ingestion and indexing are deterministic given the committed fixtures, so the
generated SQLite database and downstream artifacts are reproducible. Where any
ordering could vary, the code sorts explicitly. The evaluation harness (M8) emits
the same numbers on every run from the same inputs.

### End-to-end run (assembled across milestones)

```bash
python3 scripts/01_ingest_fixtures.py            # M2  -> results/raw/bioscientist.db
python3 scripts/02_build_index.py                # M3  -> search index
python3 scripts/03_extract_claims.py             # M4  -> results/processed/claims.{json,csv}
python3 scripts/04_build_evidence_table.py       # M5  -> results/processed/evidence_table.csv
python3 scripts/05_generate_visualizations.py    # M7  -> results/figures/*
python3 scripts/06_run_eval.py                   # M8  -> results/processed/eval_report.json
```

Each script is a thin, install-free wrapper around the package and prints exactly
what it wrote. The canonical numbers are mirrored into `docs/RESULTS.md`.

### What is committed vs. regenerated

- **Committed:** source, fixtures, gold labels, docs, website, this scaffold.
- **Regenerated (gitignored):** everything under `results/` (db, tables, figures)
  and any `data/cache/` — all reproducible from fixtures.

### Optional extras

```bash
pip install -e '.[viz]'      # matplotlib, for figures (M7)
pip install -e '.[duckdb]'   # optional DuckDB backend
pip install -e '.[llm]'      # opt-in real LLM adapter (M10); never required
```

## Driving the build (autonomous milestones)

```bash
./scripts/run_all_milestones_with_claude.sh         # milestones 0..12
./scripts/run_all_milestones_with_claude.sh 3 5     # a specific range
```

Each milestone runs as a single `claude -p` invocation under
`.claude/settings.json` (no push, no network fetch, no secret reads), commits
locally, and the runner stops on any failure, dirty tree, or missing commit.
Per-milestone logs are written under `logs/` (gitignored).

## Limitations

- Reproducibility guarantees apply to the offline fixture/cache path. Optional
  live connectors depend on third-party availability and are not deterministic.
- Floating-point or library-version differences could perturb clustering at the
  margins; results are reported with that caveat.
