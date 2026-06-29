# bioscientist-os: implementation plan

## TL;DR

`bioscientist-os` is a CPU-first research workbench for biomedical scientists.
It ingests small paper corpora, normalizes them, searches and clusters them,
extracts **structured claims** from abstracts with transparent non-LLM baselines,
links claims to biological entities and database records, and assembles
**evidence tables** in which every cell carries explicit provenance. The end
artifact is not a summary — it is an inspectable chain:

```
paper -> extracted claim -> biological entities -> database links -> support / conflict / uncertainty -> visual report
```

This document is the authoritative milestone plan. The milestone runner
(`scripts/run_all_milestones_with_claude.sh`) reads this file and `CLAUDE.md`,
implements **exactly one milestone per invocation**, and commits locally.

## Methodological question

> How can a biomedical research assistant make evidence provenance explicit
> enough that scientists can inspect claims, supporting papers, database links,
> conflicts, and uncertainty — rather than receiving opaque summaries?

The contribution we aim for is *methodological and infrastructural*: a
reproducible, auditable pipeline whose every output can be traced back to a
specific paper, snippet, and extraction method, and which honestly separates
four epistemic levels:

1. **directly observed metadata** (title, authors, year, IDs);
2. **extracted claim** (a sentence/relation pulled from text by a named method);
3. **inferred relation** (a link asserted by combining records);
4. **unsupported hypothesis** (a suggestion, explicitly not evidence).

## Design principles

- **CPU-first, offline-first.** Everything in the default path runs on an
  `m5.2xlarge`-class CPU instance with no GPU and no paid API. Tests run fully
  offline from committed fixtures.
- **Provenance is a first-class field, not a footnote.** Every claim, link, and
  table cell records where it came from (paper id, snippet span, extraction
  method, data source = fixture / cache / live).
- **Transparent baselines before clever models.** Rule-based and lexical methods
  first; any LLM is an optional, disabled-by-default, cost-guarded adapter.
- **Honest about limitations.** No overclaiming of NLP sophistication, recall,
  or biological correctness. Denominators and method labels are always shown.
- **Non-clinical.** This is a literature/database research assistant, never a
  diagnostic or treatment tool. See `docs/SAFETY.md`.
- **Every milestone leaves the repo clean and runnable.** Tests pass, no
  secrets, no large blobs, working tree clean after commit.

## Constraints

- CPU-only by default; no GPU required for core functionality.
- No paid APIs in the default path; live connectors are optional and
  fixture/cache-backed.
- Default tests are offline and run from small committed fixtures.
- Do not commit large datasets, model weights, secrets, API keys, or caches.
- Optional LLM/API integration is adapter-based, mockable, and never required
  for tests or CI.

## Non-goals

This repository is **not**:

- a medical-advice, diagnostic, or treatment-recommendation tool;
- a clinical decision-support system;
- a claim that its extraction matches expert curation quality;
- a large-scale paid-API knowledge-graph build;
- a web SaaS product;
- a tutorial or chatbot demo.

## Target repository layout

```
src/bioscientist_os/
  __init__.py
  schemas.py            # pydantic models (Paper, Author, BiomedicalEntity,
                        #   Claim, EvidenceItem, DatabaseRecord, EvidenceTable,
                        #   ResearchQuestion, WorkbenchRun)
  cli.py                # `biosci` CLI entry point (typer)
  ingest/               # fixture loaders + normalization
  search/               # lexical / TF-IDF search + topic grouping
  evidence/             # entity + claim extraction, evidence-table builder
  databases/            # connector interface + fixture/cache/live adapters
  visualization/        # timeline, clusters, evidence matrix, link graph
  storage/              # sqlite (default) / duckdb (optional) persistence
  evals/                # evaluation harness + gold-label scoring

scripts/
  run_all_milestones_with_claude.sh   # autonomous milestone runner
  00_check_environment.py             # offline environment report
  01_ingest_fixtures.py               # (created in M2)
  02_build_index.py                   # (created in M3)
  03_extract_claims.py                # (created in M4)
  04_build_evidence_table.py          # (created in M5)
  05_generate_visualizations.py       # (created in M7)
  06_run_eval.py                      # (created in M8)

data/fixtures/
  papers/        uniprot/        opentargets/      # small, clearly-marked fixtures
results/
  raw/           processed/      figures/          # reproducible, gitignored outputs
docs/
  PLAN.md METHODOLOGY.md RESULTS.md LIMITATIONS.md REPRODUCIBILITY.md
  SAFETY.md DATABASES.md EVALUATION.md ARCHITECTURE.md DATA_MODEL.md
  WEBSITE_NOTES.md  prompts/  milestones/  review_notes/  commits/
site/            # multi-page static website (committed HTML, no build step)
tests/
```

## Provenance / epistemic vocabulary (used throughout)

| Level | Field examples | Example |
|-------|----------------|---------|
| observed metadata | `paper_id`, `year`, `journal` | "PMID-fixture-007, 2021, *Cell*" |
| extracted claim | `claim_text`, `extraction_method`, `source_snippet` | "senescent cells secrete IL-6 (rule:SVO, snippet 3)" |
| inferred relation | `relation`, `entity_ids`, `inference_basis` | "senescence —associated_with→ inflammation" |
| unsupported hypothesis | `hypothesis`, `status=unsupported` | "clearing senescent cells may reduce inflammation (UNTESTED)" |

Every evidence-table cell and every memo line is tagged with one of these.

---

## Milestones

Each milestone is one runner invocation. The runner stops between milestones on:
Claude failure, no new commit, dirty tree, or pytest failure.

### Milestone 0 — Package skeleton and runnable contract

Create the Python package skeleton so the repo is an importable, testable
package. The project contract (this PLAN, `CLAUDE.md`, docs skeleton, website
shell, runner, permission policy, `.gitignore`, `pyproject.toml`) already exists
from the pre-milestone setup commit; Milestone 0 makes it *executable code*.

Deliverables:

- `src/bioscientist_os/__init__.py` (version, package docstring).
- `src/bioscientist_os/cli.py` — `biosci` CLI with at least `info`,
  `version`, and `env-check` subcommands (typer).
- Empty-but-importable subpackages: `ingest/`, `search/`, `evidence/`,
  `databases/`, `visualization/`, `storage/`, `evals/` (each with `__init__.py`).
- `tests/test_repo_contract.py` (already present) plus
  `tests/test_cli_smoke.py` and `tests/test_package_import.py`.
- Wire `scripts/00_check_environment.py` to the package where reasonable.

Validation:

- `python3 -m pytest -q` passes.
- `python3 -m bioscientist_os --help` (and `biosci --help` if installed) works.
- Website "Milestones" page marks M0 done.

Commit: `Add bioscientist-os package skeleton and CLI`

### Milestone 1 — Data schemas and small fixtures

Implement typed `pydantic` schemas: `Paper`, `Author`, `BiomedicalEntity`,
`Claim`, `EvidenceItem`, `DatabaseRecord`, `EvidenceTable`, `ResearchQuestion`,
`WorkbenchRun`. Each carries provenance fields and a `data_source` enum
(`fixture` / `cache` / `live`).

Create small, clearly-marked fixtures around a focused theme
(**cellular senescence / longevity / autophagy**):

- 15–30 paper records (title, authors, journal, year, abstract, keywords, URL,
  external IDs);
- 5–10 UniProt-style protein records;
- a handful of disease/gene/protein link records (Open Targets-style).

Where licensing/API provenance is uncertain, use **synthetic** records and mark
them as such in a `data/fixtures/README.md` and a per-record `synthetic: true`
flag.

Validation: schema round-trip tests; fixture-loads-and-validates tests;
fixtures are clearly labeled synthetic vs. derived.

Commit: `Add typed schemas and labeled biomedical fixtures`

### Milestone 2 — Ingestion and local storage

Ingest fixtures into SQLite (default; DuckDB optional) via a storage layer.

CLI:

```bash
biosci ingest data/fixtures --db results/raw/bioscientist.db
biosci stats --db results/raw/bioscientist.db
```

Tests: schema validation on ingest; ingestion count checks; duplicate handling
(idempotent re-ingest); reproducible/deterministic database creation.

Commit: `Add fixture ingestion and local storage`

### Milestone 3 — Search and topic grouping

CPU-only search: a lexical / BM25-like baseline, optional TF-IDF, simple topic
grouping/clustering, and a query-result **explanation** (which terms matched,
which fields, scores).

CLI:

```bash
biosci search "cellular senescence inflammation" --db results/raw/bioscientist.db
biosci topics --db results/raw/bioscientist.db
```

Outputs: search-result tables; a topic report. Tests on tiny labeled queries.

Commit: `Add lexical search and topic grouping`

### Milestone 4 — Entity and claim extraction baseline

A transparent, auditable, **non-LLM** baseline:

- biomedical entity recognition via dictionaries built from the fixtures;
- claim-sentence extraction from abstracts/snippets;
- optional simple relation templates (subject–verb–object, association cues);
- confidence and provenance fields on every extraction.

No overclaiming. Output extracted claims as CSV/JSON, each linked to its paper
and exact source snippet span.

Commit: `Add rule-based entity and claim extraction baseline`

### Milestone 5 — Evidence table builder

Build evidence tables grouped by a research question.

```bash
biosci evidence \
  --question "What evidence links cellular senescence to chronic inflammation?" \
  --db results/raw/bioscientist.db \
  --out results/processed/evidence_table.csv
```

Columns: `claim_id`, `claim_text`, `entity_names`, `paper_id`, `source_snippet`,
`support_conflict_unknown`, `extraction_method`, `confidence`, `database_links`,
`notes`. Tests assert provenance coverage and column completeness.

Commit: `Add evidence table builder`

### Milestone 6 — Database connector layer

Clean adapters, offline-first:

- a base connector interface;
- a fixture-backed connector (required);
- a cache layer (writes under `data/cache/`, gitignored);
- retry / error handling;
- a `provenance` field on every record (fixture / cache / live);
- optional live connectors (PubMed / Europe PMC / OpenAlex / UniProt) only if
  low-friction, **off by default**, never required for tests.

At minimum: fixture-backed UniProt-style and paper-metadata connectors.

Commit: `Add offline-first database connector layer`

### Milestone 7 — Visualizations

Generate (matplotlib, optional extra):

- literature timeline;
- topic-cluster summary;
- claim / evidence matrix;
- entity / database-link graph (networkx);
- support-vs-conflict table.

Save under `results/figures/`; document regeneration. Figure tests are skipped
when `matplotlib` is not installed (core path stays light).

Commit: `Add workbench visualizations`

### Milestone 8 — Evaluation harness

A small but rigorous evaluation of the workbench itself:

- ingestion correctness;
- search recall on hand-labeled fixture queries;
- entity-extraction precision/recall on tiny gold labels;
- claim-extraction sanity checks;
- evidence-table completeness;
- provenance coverage (% of cells with full provenance).

Report clear denominators and, where meaningful, confidence intervals
(e.g. Wilson interval for proportions). Small N is stated honestly.

```bash
biosci eval --db results/raw/bioscientist.db --out results/processed/eval_report.json
```

Commit: `Add evaluation harness with gold labels`

### Milestone 9 — End-to-end research memo generation

Generate a structured research memo from the fixture corpus. The memo includes:
research question, key papers, extracted claims, evidence table, database links,
conflicts/uncertainties, suggested next experiments **as hypotheses only**,
limitations, and exact provenance. **No medical advice.**

```bash
biosci memo --question "..." --db results/raw/bioscientist.db --out results/processed/memo.md
```

Commit: `Add end-to-end research memo generator`

### Milestone 10 — Optional LLM adapter (not required)

An optional adapter interface for LLM-assisted claim extraction / memo polish:

- a **mock adapter** used in all tests;
- a cost guard (`--max-cost-usd`, dry-run);
- a response cache;
- disabled-by-default behavior;
- no paid API required for CI.

If a real adapter would slow the project, ship only the interface + mock.

Commit: `Add optional, cost-guarded LLM adapter interface`

### Milestone 11 — Website, final report, and portfolio polish

Update README, docs, and the multi-page website to reflect what exists, what is
prototype-only, measured results, what the system does **not** claim, why it is
useful to biomedical scientists, and how it could become a research paper.

Commit: `Polish website, results, and portfolio documentation`

### Milestone 12 — Final cleanup and quality gates

Run tests, lint, smoke scripts, and a hygiene/secret check; confirm the website
is viewable; confirm no large data/secrets/weights/caches are committed; confirm
the end-to-end run reproduces all artifacts. Finalize `docs/RESULTS.md`,
`docs/LIMITATIONS.md`, `docs/REPRODUCIBILITY.md`, `docs/SAFETY.md`, and create
`docs/PAPER_PATH.md` (honest about prototype status).

Commit: `Finalize bioscientist-os research workbench`

---

## Quality gates (project is not complete unless)

- `pytest` passes from a clean checkout (offline).
- Fixture ingestion works from scratch.
- One end-to-end run produces: local database, search results, extracted claims,
  evidence table, visualizations, research memo, and evaluation report.
- Docs explain how to reproduce the end-to-end run.
- The website is viewable locally (static HTML, no build step required).
- No large data / secrets / weights / caches are committed.
- The git working tree is clean after each milestone commit.

## Research questions (revisited at Milestone 12)

- How much of a literature claim's *credibility* can be made inspectable purely
  from metadata + transparent extraction, with no opaque model in the loop?
- What provenance fields are necessary for a scientist to *audit* an evidence
  table rather than trust it?
- Where do rule-based baselines fail, and which failures would an LLM adapter
  plausibly fix vs. merely obscure?
- Can support/conflict/uncertainty be surfaced reliably enough to be useful
  without overclaiming biological correctness?

## Expected final artifact

A serious reviewer should be able to: install the repo offline; ingest the
fixtures; run a search; extract claims; build an evidence table with visible
provenance; generate figures, a memo, and an evaluation report; read a clear
multi-page website; and understand precisely what is proven, what is prototype,
and what the system explicitly does not claim.
