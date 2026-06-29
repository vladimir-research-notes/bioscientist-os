# Claude Code instructions for this repository

This repository is `bioscientist-os`: a CPU-first, evidence-centered research
workbench for biomedical scientists. It is a serious research artifact, not a
chatbot demo or tutorial.

Read `docs/PLAN.md` before doing anything. It is the authoritative milestone
plan and the single source of truth for what each milestone must deliver.

## Public framing

`bioscientist-os` ingests small biomedical paper corpora, normalizes them,
searches and clusters them, extracts **structured claims** with transparent
non-LLM baselines, links claims to biological entities and database records, and
assembles **evidence tables** in which every cell carries explicit provenance.
The key artifact is the inspectable chain, not a summary:

```
paper -> extracted claim -> biological entities -> database links -> support / conflict / uncertainty -> visual report
```

## Operating principles

- Build milestone by milestone, in the order defined in `docs/PLAN.md`.
- Implement **exactly one milestone per run**. Do not implement later milestones.
- Commit locally after each coherent milestone. **Do not push.**
- Do not wait for human review; create a review placeholder and continue.
- Keep the default path CPU-only and offline: no GPU, no paid API, no network
  required for tests.
- Tests run from small committed fixtures only.
- Any LLM/API integration is optional, disabled by default, mock-backed in
  tests, and protected by an explicit cost guard.
- Prefer transparent rule-based / lexical baselines before any model.
- Do not commit secrets, API keys, virtualenvs, caches (`data/cache/`,
  `.pytest_cache`, etc.), `node_modules`, model weights, large datasets,
  generated `results/` artifacts, or `.claude/settings.local.json`.
- Avoid marketing language. Documentation is precise, technical, and honest
  about limitations. Do not overclaim NLP sophistication or biological
  correctness.

## Safety / non-clinical use (hard constraint)

`bioscientist-os` is a research-assistance tool, **not** a medical-advice tool.

- No patient-specific clinical decision support.
- No diagnosis, treatment recommendation, or drug-efficacy claims.
- Every generated summary/memo must clearly distinguish:
  1. directly observed metadata,
  2. extracted claim,
  3. inferred relation,
  4. unsupported hypothesis.
- Evidence provenance must always be visible.

See `docs/SAFETY.md`. Any output that could read as clinical advice is a defect.

## Provenance discipline

Every claim, link, and evidence-table cell must record its provenance:
`paper_id`, `source_snippet` (with span where possible), `extraction_method`,
and `data_source` (`fixture` / `cache` / `live`). A result without provenance is
incomplete and should fail review.

## Quality bar

Every major claim should be backed by at least one of: a test, a reproducible
example command, a result table/figure, a documented limitation, or an explicit
non-goal. The repo should be understandable to a strong senior engineer or
biomedical researcher after 5 minutes and survive deeper questioning after 30.

## Required behavior after each milestone

1. Run that milestone's tests and smoke commands.
2. Update the multi-page website under `site/` (at least the relevant page and
   the Milestones page status).
3. Update `docs/RESULTS.md` or the relevant doc if results changed.
4. Create or update `docs/milestones/XX-<name>.md` (milestone note).
5. Create or update `docs/review_notes/XX-<name>-human-review.md` (placeholder).
6. Create or update `docs/commits/XX-<name>.md` (commit note) if used.
7. `git add -A` and commit locally with a specific, professional message.
8. Print: milestone title, commit hash, tests run, website pages updated,
   review placeholder path, and the next milestone.

Before committing: run relevant tests, run the relevant smoke script, check
`git status`, and confirm no secrets / caches / large data / virtualenvs are
staged.

Do not stop for review unless continuing would risk secrets, paid API spend,
data loss, or repository corruption.

## Review-note format

`docs/review_notes/XX-<name>-human-review.md`:

```
# Human review: <milestone title>

## TL;DR
## What changed
## Commands run
## Test status
## Known limitations
## Possible misleading artifacts
## Human feedback
<!-- Human will fill this later. -->
```

Do not claim that human review happened.

## Website requirements

A multi-page static website lives under `site/` (plain committed HTML + one
`style.css`; no build step, viewable via `file://`). Required pages:

`index.html` (Overview), `architecture.html`, `data-model.html`,
`ingestion.html`, `evidence.html`, `databases.html`, `visualizations.html`,
`evaluation.html`, `results.html`, `limitations.html`, `safety.html`,
`reproducibility.html`, `roadmap.html`, `milestones.html`.

Each page contains: a brief explanation, a deeper technical explanation, current
implementation status, relevant files, current test/result status, and open
questions / limitations. Update the website at every milestone so it reflects
what actually exists and what tests/results currently show — never describe
unimplemented features as done.

## How milestones are launched

The human launches milestones with `scripts/run_all_milestones_with_claude.sh`
(one `claude -p` run per milestone). The runner stops on any failure, dirty
tree, or missing commit. You are invoked with "Implement Milestone N only."
Honor that boundary exactly.
