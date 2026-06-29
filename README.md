# bioscientist-os

**A CPU-first, evidence-centered research workbench for biomedical literature.**

`bioscientist-os` helps a biomedical scientist move from *papers* to *inspectable
evidence*. It ingests small paper corpora, normalizes them, searches and clusters
them, extracts **structured claims** from abstracts using transparent (non-LLM)
baselines, links those claims to biological entities and database records, and
builds **evidence tables** in which every cell carries explicit provenance.

The key artifact is not a summary. It is an auditable chain:

```
paper -> extracted claim -> biological entities -> database links -> support / conflict / uncertainty -> visual report
```

> **Status:** early scaffold. This commit establishes the project contract
> (plan, docs, website, permission policy, and an autonomous milestone runner).
> Functional code is built milestone by milestone — see
> [`docs/PLAN.md`](docs/PLAN.md) and the live status on the website's
> *Milestones* page. Do not read unimplemented milestones as done.

## Why this exists

Scientists increasingly receive *opaque* AI summaries of literature. This project
asks a narrower, more honest question:

> How can a biomedical research assistant make evidence provenance explicit
> enough that scientists can inspect claims, supporting papers, database links,
> conflicts, and uncertainty — rather than trusting a black-box summary?

Every output separates four epistemic levels: **observed metadata**,
**extracted claim**, **inferred relation**, and **unsupported hypothesis**.

## Non-clinical use

This is a research-assistance tool for literature and public-database metadata.
It is **not** a medical device and gives **no** diagnosis, treatment, or
drug-efficacy advice. See [`docs/SAFETY.md`](docs/SAFETY.md).

## Design constraints

- CPU-only by default (target: AWS `m5.2xlarge`-class instance); no GPU.
- No paid APIs in the default path; external connectors are fixture/cache-backed.
- Tests run fully offline from small committed fixtures.
- No large datasets, model weights, secrets, or caches are committed.
- Any LLM integration is optional, disabled by default, mock-backed, cost-guarded.

## Quickstart (CPU-only, offline)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Environment report (no network, no paid API):
python3 scripts/00_check_environment.py

# Run the test suite (offline):
python3 -m pytest -q
```

The planned end-to-end run (built across milestones) will be:

```bash
biosci ingest data/fixtures --db results/raw/bioscientist.db   # M2
biosci search "cellular senescence inflammation" --db results/raw/bioscientist.db   # M3
biosci evidence --question "What evidence links cellular senescence to chronic inflammation?" \
  --db results/raw/bioscientist.db --out results/processed/evidence_table.csv        # M5
biosci memo --question "..." --db results/raw/bioscientist.db --out results/processed/memo.md  # M9
```

## Repository layout

```
src/bioscientist_os/   schemas, CLI, ingest/search/evidence/databases/visualization/storage/evals
scripts/               environment check + numbered pipeline scripts + milestone runner
data/fixtures/         small, clearly-labeled paper / UniProt / Open Targets fixtures
results/               reproducible outputs (db, tables, figures) — gitignored
docs/                  PLAN, METHODOLOGY, RESULTS, LIMITATIONS, SAFETY, ... + milestone notes
site/                  multi-page static website (open site/index.html)
tests/                 offline pytest suite
```

## How development is driven

This repo is built by an autonomous, milestone-at-a-time process. The human
launches:

```bash
./scripts/run_all_milestones_with_claude.sh        # all milestones (0..12)
./scripts/run_all_milestones_with_claude.sh 3 5    # a range
```

Each invocation runs `claude -p` for **one** milestone under a strict permission
policy (`.claude/settings.json`: no push, no network fetch, no secret reads),
commits locally, and stops on any failure or dirty tree. See
[`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) and `CLAUDE.md`.

## Documentation

- [`docs/PLAN.md`](docs/PLAN.md) — milestone plan and design principles
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — pipeline and provenance model
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — schemas
- [`docs/DATABASES.md`](docs/DATABASES.md) — connector design
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — evaluation methodology
- [`docs/RESULTS.md`](docs/RESULTS.md) — measured results (populated by milestones)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — honest limitations
- [`docs/SAFETY.md`](docs/SAFETY.md) — non-clinical-use statement
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) — how to reproduce everything

## License

MIT — see [`LICENSE`](LICENSE).
