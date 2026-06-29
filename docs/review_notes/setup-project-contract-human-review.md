# Human review: Project setup (pre-milestone contract)

## TL;DR
Establishes the `bioscientist-os` project contract before any milestone runs:
the milestone plan (`docs/PLAN.md`), operating instructions (`CLAUDE.md`), a full
docs skeleton, a 14-page static website (status-aware), the autonomous milestone
runner (`scripts/run_all_milestones_with_claude.sh`), a strict Claude permission
policy (`.claude/settings.json`), an offline environment-check script, and a
dependency-free contract test suite. No functional package code yet — that begins
at Milestone 0, which the human launches.

## What changed
- Added `README.md`, `CLAUDE.md`, `LICENSE`, `pyproject.toml`, `requirements.txt`,
  `.gitignore`, `conftest.py`.
- Added `docs/`: PLAN, METHODOLOGY, ARCHITECTURE, DATA_MODEL, DATABASES,
  EVALUATION, RESULTS, LIMITATIONS, REPRODUCIBILITY, SAFETY, ROADMAP,
  WEBSITE_NOTES, plus `prompts/`, `milestones/`, `review_notes/`, `commits/`
  (with READMEs / placeholders).
- Added `site/`: 14 pages + `style.css` (Overview, Architecture, Data model,
  Ingestion, Evidence tables, Database connectors, Visualizations, Evaluation,
  Results, Milestones, Reproducibility, Limitations, Safety, Roadmap).
- Added `scripts/run_all_milestones_with_claude.sh` (runner) and
  `scripts/00_check_environment.py` (offline env report).
- Added `.claude/settings.json` (acceptEdits; denies push, curl/wget, rm, secret
  reads, local settings read).
- Added `tests/test_repo_contract.py` (8 dependency-free tests).
- Created the directory skeleton: `src/bioscientist_os/`, `data/fixtures/{papers,
  uniprot,opentargets}`, `results/{raw,processed,figures}`.

## Commands run
- `python3 scripts/00_check_environment.py` — runs; reports BLOCKED in the system
  Python because core deps are not installed there (expected; use a venv).
- `python3 -m pytest -q` — 8 passed.
- HTML well-formedness check across all 14 site pages — all OK.

## Test status
8 passed (contract tests). No functional tests yet; those land with each milestone.

## Known limitations
- This commit is scaffold + contract only; there is no schema, ingestion, search,
  extraction, evidence, connector, visualization, evaluation, or memo code yet.
- The website's *Milestones* page lists every milestone as "Planned"; the runner
  flips status as milestones complete.
- `docs/RESULTS.md` is intentionally near-empty (no measured numbers yet).

## Possible misleading artifacts
- The website looks complete but describes mostly *planned* functionality. Status
  badges ("Scaffold"/"Planned") and the Milestones page are the source of truth;
  no page claims an unimplemented feature is done.
- `scripts/00_check_environment.py` reports the `sqlite3` *CLI* as "not found";
  storage uses Python's stdlib `sqlite3` module (always available), not the CLI.

## Human feedback
<!-- Human will fill this later. -->
