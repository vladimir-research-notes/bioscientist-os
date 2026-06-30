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

> **Status:** working prototype. **All 13 milestones (0–12)** of the
> [13-milestone plan](docs/PLAN.md) have landed, including the final cleanup /
> quality-gate pass (M12; green gates recorded in
> [`docs/RESULTS.md`](docs/RESULTS.md)). The whole pipeline runs **CPU-only and offline**:
> the repository is an importable package with a runnable `biosci` CLI (`version`,
> `info`, `env-check`, `ingest`, `stats`, `search`, `topics`, `extract`, `evidence`,
> `db`, `figures`, `eval`, `memo`, `llm`); typed schemas + labeled fixtures ingest
> into a deterministic SQLite database; the corpus is searchable (BM25F) and
> groupable into topics; a transparent non-LLM baseline recognizes entities and
> extracts claims; the workbench assembles **evidence tables** grouped by a research
> question, every cell with provenance, database links, and a heuristic
> support/conflict/unknown signal; an offline-first **database-connector layer**
> serves records with an explicit `data_source` provenance (fixture / cache / live);
> the workbench generates five **figures** (timeline, topic clusters, evidence
> matrix, link graph, support-vs-conflict) — inspectable data always, PNGs when the
> optional `matplotlib` extra is installed; a gold-label **self-evaluation** scores
> the pipeline (ingestion, search recall, entity precision/recall, claim sanity,
> evidence completeness, provenance coverage) with explicit denominators and Wilson
> intervals; and the workbench assembles an end-to-end **research memo** per
> question, with suggested experiments emitted only as explicitly unsupported
> hypotheses and no medical advice. An **optional, cost-guarded LLM adapter**
> (mock / cache / opt-in Anthropic) exists but is kept **off the default path** — the
> pipeline and the entire test suite use no language model. **274 offline tests
> pass** (1 skipped without `matplotlib`). See the live status on the website's
> *Milestones* page; nothing here describes an unimplemented feature as done.

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

# If pip reports "externally managed environment" (PEP 668) or venv creation
# fails ("ensurepip is not available"), use the no-sudo uv path instead:
#   pip install --user --break-system-packages uv
#   uv venv .venv && uv pip install -e '.[dev]' && source .venv/bin/activate
# See docs/REPRODUCIBILITY.md. Docker is not required for this CPU-only project.

# Environment report (no network, no paid API):
python3 scripts/00_check_environment.py
biosci env-check          # same report, via the installed CLI

# Inspect the tool's identity, epistemic levels, and safety stance:
biosci info               # (or: python3 -m bioscientist_os info)

# Run the test suite (offline):
python3 -m pytest -q
```

The end-to-end run (the full pipeline; every artifact below is reproducible from
the committed fixtures and gitignored):

```bash
biosci ingest data/fixtures --db results/raw/bioscientist.db   # M2
biosci search "cellular senescence inflammation" --db results/raw/bioscientist.db   # M3
biosci extract --db results/raw/bioscientist.db   # M4
biosci evidence --question "What evidence links cellular senescence to chronic inflammation?" \
  --db results/raw/bioscientist.db --out results/processed/evidence_table.csv        # M5
biosci db lookup --source uniprot --id P05231 --db results/raw/bioscientist.db   # M6
biosci figures --db results/raw/bioscientist.db   # M7 (PNGs need: pip install -e '.[viz]')
biosci eval --db results/raw/bioscientist.db --out results/processed/eval_report.json  # M8
biosci memo --question "What evidence links cellular senescence to chronic inflammation?" \
  --db results/raw/bioscientist.db --out results/processed/memo.md   # M9
biosci llm info   # M10 (optional adapter, off the default path; mock-only on the CLI)
```

See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for the script-based
equivalent (`scripts/01_…` through `scripts/08_…`) and the determinism guarantees.

## Measured results (on the committed fixtures)

These are produced by `biosci eval` against committed gold labels and reproduced in
[`docs/RESULTS.md`](docs/RESULTS.md). They measure **pipeline behaviour on a tiny,
partly-synthetic corpus** — not population performance or biological truth. Small N
means wide intervals; that is the point of reporting the interval, not the bare
percentage.

| Metric | Value (95% Wilson CI) | Denominator |
|--------|-----------------------|-------------|
| ingestion correctness | 1.000 [0.912, 1.000] | 40 / 40 fixture records |
| search recall@3 (micro) | 0.875 [0.640, 0.965] | 14 / 16 relevant pairs |
| search recall@5 (micro) | 1.000 [0.806, 1.000] | 16 / 16 relevant pairs |
| entity precision | 1.000 [0.851, 1.000] | 22 / 22 recognized |
| entity recall | 0.917 [0.742, 0.977] | 22 / 24 gold entities |
| claim sanity (well-formed + span-traceable) | 1.000 [0.916, 1.000] | 42 / 42 claims |
| evidence completeness | 1.000 [0.947, 1.000] | 68 / 68 rows |
| provenance coverage | 1.000 [0.947, 1.000] | 68 / 68 rows |

The dictionary recognizer is high precision by construction and loses on recall;
both misses are deliberate and documented (`data/fixtures/gold/README.md`). Claim
sanity, completeness, and provenance are 1.0 **by construction** and serve as
regression floors, not achievements.

## Who this is for, and what it is *not*

It is aimed at a biomedical scientist or research engineer who wants to move from
papers to an **auditable evidence table** — and who would rather inspect a claim's
paper, snippet, extraction method, database links, and support/conflict signal than
trust an opaque summary. Every output separates four epistemic levels and links each
cell to its source.

**What this does *not* claim:**

- It is **not** a medical-advice, diagnostic, treatment, or clinical-decision tool,
  and gives no drug-efficacy/safety/dosing statements (see
  [`docs/SAFETY.md`](docs/SAFETY.md)). Output that reads as clinical advice is a defect.
- It does **not** match expert-curation quality. Entity recognition is
  dictionary-based (misses synonyms and novel entities); claim extraction is
  rule/template-based (limited recall, brittle to paraphrase and negation).
- "Support / conflict / unknown" is a **heuristic textual signal**, not an
  adjudication of biological correctness or study quality. In particular it does not
  detect cross-paper *directional* conflict by itself.
- The numbers above are **not** a benchmark or a state-of-the-art claim; they certify
  that the pipeline behaves as specified on a small, theme-focused fixture set.
- The optional LLM adapter adds **no measured pipeline capability** and never speaks
  as a transparent baseline; model output is the least-trusted, `unsupported_hypothesis`
  level.

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the full list.

## From prototype to a research paper

The contribution this prototype aims at is *methodological and infrastructural*: a
reproducible, auditable pipeline whose every output traces back to a specific paper,
snippet, and extraction method, and which never collapses the four epistemic levels.
That is a platform, not yet a result. A credible empirical paper would need at least:
larger, properly-licensed corpora with multi-annotator gold labels; **gold
support/conflict annotations** so the support label can be scored against a human
verdict (today only the table's *structural* quality is measured); ontology-grounded
entity linking that preserves auditability; a controlled comparison of transparent
baselines vs. an optional LLM adapter on *provenance fidelity*; and — the core
payoff — a user study of which provenance fields actually change a scientist's trust
or decision. These are directions, not promises; a candid assessment of what the
prototype establishes, what is missing, and the threats to validity is in
[`docs/PAPER_PATH.md`](docs/PAPER_PATH.md). See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Repository layout

```
src/bioscientist_os/   schemas, CLI, ingest/search/evidence/databases/visualization/storage/evals/llm
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
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — package layout and pipeline
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — pipeline and provenance model
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — schemas
- [`docs/DATABASES.md`](docs/DATABASES.md) — connector design
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — evaluation methodology
- [`docs/LLM_ADAPTER.md`](docs/LLM_ADAPTER.md) — optional, off-by-default LLM adapter
- [`docs/RESULTS.md`](docs/RESULTS.md) — measured results (populated by milestones)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — honest limitations
- [`docs/SAFETY.md`](docs/SAFETY.md) — non-clinical-use statement
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) — how to reproduce everything
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — research directions and the path to a paper
- [`docs/PAPER_PATH.md`](docs/PAPER_PATH.md) — candid prototype→paper assessment (gaps, threats to validity)

## License

MIT — see [`LICENSE`](LICENSE).
