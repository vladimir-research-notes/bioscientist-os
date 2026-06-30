# Architecture

## TL;DR

A single Python package (`src/bioscientist_os/`) with narrow, testable
subpackages, a `typer` CLI (`biosci`), SQLite storage by default, and a static
website. No services, no GPU, no network in the default path.

## Short explanation

```
                    data/fixtures/  (papers, uniprot, opentargets)
                            |
                        ingest/  --->  storage/ (sqlite/duckdb)  <--- databases/ (connectors)
                            |                 |                              |
                        search/  ----  evidence/ (entities, claims,  -------+
                            |                evidence tables)
                            |                 |
                     visualization/      evals/
                            |                 |
                          site/ + results/figures + research memo
```

The `cli.py` module wires subcommands to subpackages. Each subpackage is
independently importable and unit-tested.

## Longer explanation

| Subpackage | Responsibility | Introduced |
|------------|----------------|------------|
| `schemas.py` | pydantic models + provenance/epistemic fields | M1 |
| `ingest/` | fixture loaders, normalization | M2 |
| `storage/` | sqlite (default) / duckdb persistence | M2 |
| `search/` | BM25F lexical + TF-IDF search, single-link topic grouping **(done, M3)** | M3 |
| `evidence/` | entity + claim extraction, evidence-table builder | M4–M5 |
| `databases/` | connector interface, fixture/cache/live adapters | M6 |
| `visualization/` | timeline, clusters, matrix, link graph | M7 |
| `evals/` | gold-label evaluation harness | M8 |
| `cli.py` | `biosci` command surface | M0+ |

**Storage.** SQLite is the default (stdlib, zero-dependency, deterministic file
output). DuckDB is an optional backend for analytical queries.

**Determinism.** Ingestion and indexing are deterministic given fixed fixtures,
so database creation and results are reproducible (a property tested in M2/M8).

**Optionality.** `matplotlib` (figures) and `anthropic` (LLM adapter) are
optional extras; the core import path and default tests do not require them.

## Exact commands

```bash
python3 -m bioscientist_os --help        # CLI surface (after M0)
python3 -m pytest -q                     # offline test suite
```

## Limitations

- Single-process, local-only; no concurrency or service layer (out of scope).
- The connector "live" mode is optional and best-effort; correctness guarantees
  apply to the fixture/cache path.
- Current implementation status per subpackage is tracked on the website's
  *Milestones* page and in `docs/milestones/`.
