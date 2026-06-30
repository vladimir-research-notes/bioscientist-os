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

No network (after install), no GPU, no paid API are required for any of the above.

### If `pip install` says "externally managed environment" (PEP 668)

Modern Ubuntu marks the **system** Python as externally managed, so installing
into it is blocked — always use a virtualenv. If `python3 -m venv .venv` itself
fails with *"ensurepip is not available"*, the host is missing `python3.12-venv`.
Two fixes:

```bash
# Recommended — no sudo, fast, reproducible (uv bundles its own bootstrap):
pip install --user --break-system-packages uv     # one-time, installs to ~/.local/bin
uv venv .venv
uv pip install -e '.[dev]'
source .venv/bin/activate

# Or the standard one-time-sudo route:
sudo apt-get install -y python3.12-venv
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Docker is **not** needed for this CPU-only, offline-by-default project; a venv is
lighter and matches the lowest-friction design.

## Longer explanation

### Determinism

Ingestion and indexing are deterministic given the committed fixtures, so the
generated SQLite database and downstream artifacts are reproducible. Where any
ordering could vary, the code sorts explicitly. Concretely (M2): ingestion writes
no timestamps or run ids, structured sub-fields are stored as canonical
sorted-key JSON, and `SQLiteStore.content_digest()` hashes every row in
primary-key order — so `biosci stats` reports the **same SHA-256 content digest**
on every build from the same fixtures, and re-ingesting is an idempotent UPSERT
that never creates duplicate rows. (Raw `.db` bytes can still differ across
libsqlite versions; the content digest is the robust, logical guarantee.) Search
and topic grouping (M3) are likewise deterministic: the in-memory index is a pure
function of the database, BM25F hits sort by score then `paper_id` (a stable
tie-break), and topic groups, members, and labels are all sorted — so a query and
a topic report reproduce exactly on every build. Entity/claim extraction (M4) is
also a pure function of the database: the dictionary is rebuilt from the ingested
records, papers are processed in `paper_id` order, results stay in document order,
and every span is the verbatim `abstract[start:end]` — so
`results/processed/claims.json` is byte-identical across runs. Evidence-table
assembly (M5) is the same: questions resolve deterministically, claims are kept in
corpus order, database links and rows are sorted, and rows are ordered by
`(-confidence, paper_id, claim_id)` — so `results/processed/evidence_tables.json`
is byte-identical across runs. Figure generation (M7) is likewise a pure function
of the database: it re-presents the M3/M4/M5 reports and sorts every series, node,
and edge before emitting them, so `results/figures/visualizations.json` is
byte-identical across runs. Only the optional PNG bytes can vary (across
`matplotlib` versions/fonts); the network-graph layout is seeded so a render is at
least visually stable run-to-run. The evaluation harness (M8) is a pure function of
the ingested corpus and the committed gold labels — its evaluators sort every
per-query/per-abstract/per-question detail before emitting it — so
`results/processed/eval_report.json` is byte-identical across runs.

### End-to-end run (assembled across milestones)

```bash
python3 scripts/01_ingest_fixtures.py            # M2  -> results/raw/bioscientist.db
python3 scripts/02_build_index.py                # M3  -> search index
python3 scripts/03_extract_claims.py             # M4  -> results/processed/claims.{json,csv}
python3 scripts/04_build_evidence_table.py       # M5  -> results/processed/evidence_table.csv
python3 scripts/05_generate_visualizations.py    # M7  -> results/figures/*
python3 scripts/06_run_eval.py                   # M8  -> results/processed/eval_report.json
python3 scripts/07_generate_memo.py              # M9  -> results/processed/memo.md
python3 scripts/08_llm_adapter_demo.py           # M10 -> offline LLM-adapter demo (no artifacts)
```

The M10 demo is **off the pipeline**: it needs no database and writes nothing
committed — it exercises the optional LLM adapter (cost guard, dry-run, mock, cache)
fully offline with no paid API and no API key.

Each script is a thin, install-free wrapper around the package and prints exactly
what it wrote. The canonical numbers are mirrored into `docs/RESULTS.md`.

Once the database exists, search and topic grouping can be driven directly
(offline, CPU-only):

```bash
biosci search "cellular senescence inflammation" --db results/raw/bioscientist.db
biosci search "IL-6 SASP senescence" --db results/raw/bioscientist.db --explain
biosci topics --db results/raw/bioscientist.db --threshold 0.15
biosci extract --db results/raw/bioscientist.db --paper biosci-paper-006
biosci evidence --db results/raw/bioscientist.db \
  --question "What evidence links cellular senescence to chronic inflammation?" \
  --out results/processed/evidence_table.csv
biosci db sources --db results/raw/bioscientist.db
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db
biosci memo --db results/raw/bioscientist.db \
  --question "What evidence links cellular senescence to chronic inflammation?" \
  --out results/processed/memo.md
biosci llm info
biosci llm complete "Summarize the senescence ↔ inflammation evidence." --task polish
biosci llm complete "estimate" --input-price 3 --output-price 15 --max-cost-usd 9 --dry-run
```

`biosci search --explain` prints, per hit, each query term's idf, the fields it
matched in, and its additive score contribution (the contributions sum to the
hit's score). `--json` emits the same structure for downstream use. `biosci
extract` recognizes dictionary entities and entity-grounded claim sentences from
abstracts, each with a confidence and an exact source-snippet span;
`scripts/03_extract_claims.py` writes `results/processed/claims.{json,csv}` and
`entities.csv` (gitignored, regenerable). `biosci evidence` builds an evidence
table for a research question — every row with full provenance, database links,
and a heuristic support/conflict/unknown label;
`scripts/04_build_evidence_table.py` writes one `evidence_<question_id>.csv` per
question plus `evidence_table.csv` and `evidence_tables.json` (gitignored,
regenerable). `biosci db` drives the offline-first connector layer (M6): `db
sources` lists the fixture connectors, `db list`/`db lookup` serve records by id with
an explicit `data_source` provenance, and `db lookup --cache` demonstrates the
read-through cache under `data/cache/` (gitignored) — the first lookup reports the
real source, the second reports `data_source=cache`. `biosci figures` (M7) builds
the five figures over the corpus and writes `results/figures/visualizations.json`
(the inspectable figure data, always) plus the PNGs when the optional `matplotlib`
extra is installed; `scripts/05_generate_visualizations.py` is the thin wrapper, and
`--no-render` writes the data only. `biosci eval` (M8) scores the pipeline against
the committed gold labels (`data/fixtures/gold/`) and writes
`results/processed/eval_report.json` — every metric with its denominator and a 95%
Wilson interval; `scripts/06_run_eval.py` is the thin wrapper. `biosci memo` (M9)
assembles the end-to-end research memo for a question — key papers (BM25F), the
evidence table, database links, conflicts/uncertainties, and suggested next
experiments emitted *only* as explicitly unsupported hypotheses — printing the
Markdown memo (or `--json` for the structured report); `scripts/07_generate_memo.py`
writes one `memo_<question_id>.md` per stored question plus `memo.md` and `memos.json`
(gitignored, regenerable). It is a research-assistance artifact, not medical advice
(see `docs/SAFETY.md`). `biosci llm` (M10) drives the **optional** LLM adapter — `llm
info` describes the layer and its safeguards, and `llm complete` runs one completion
through the deterministic, offline **mock** adapter under the cost guard (`--max-cost-usd`,
`--dry-run`, illustrative `--input-price`/`--output-price`, and `--cache`); it needs no
database, no network, and no API key. The adapter is off the pipeline and disabled by
default for the real (Anthropic) backend; `scripts/08_llm_adapter_demo.py` exercises the
whole contract offline (see `docs/LLM_ADAPTER.md`).

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
Per-milestone logs are written under `logs/` (gitignored). The runner
auto-activates `./.venv` if present (so its pytest gate and the milestone agents
use project deps, not the externally-managed system Python); activate it yourself
too if you run the pipeline scripts manually.

## Limitations

- Reproducibility guarantees apply to the offline fixture/cache path. Optional
  live connectors depend on third-party availability and are not deterministic.
- Floating-point or library-version differences could perturb clustering at the
  margins; results are reported with that caveat.
