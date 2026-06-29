# Human review: Milestone 0 — Package skeleton and runnable contract

## TL;DR
`bioscientist-os` is now an importable, testable Python package with a runnable
`biosci` CLI (`version`, `info`, `env-check`). Seven subpackages exist as
documented, importable skeletons with no domain logic yet. The offline
environment check moved into the package (`bioscientist_os.environment`) so the
CLI and `scripts/00_check_environment.py` share one implementation. 20 offline
tests pass.

## What changed
- Added `src/bioscientist_os/__init__.py` (import-light metadata: version,
  description, the four epistemic levels, the non-clinical safety note,
  subpackage list).
- Added `src/bioscientist_os/cli.py` (`typer` app; `version`, `info`,
  `env-check`) and `src/bioscientist_os/__main__.py` (`python -m bioscientist_os`).
- Added `src/bioscientist_os/environment.py` (canonical offline env report;
  stdlib-only) and rewrote `scripts/00_check_environment.py` as a thin wrapper
  that delegates to it.
- Added the seven subpackages (`ingest, search, evidence, databases,
  visualization, storage, evals`), each with a docstring naming its milestone.
- Added `tests/test_package_import.py` (7) and `tests/test_cli_smoke.py` (5).
- Removed the now-redundant `src/bioscientist_os/.gitkeep`.
- Updated the website (Milestones → M0 *Done* + a "delivered" section;
  Overview and Architecture status tables) and `docs/RESULTS.md` (build/test
  status).

## Commands run
- `python3 -m pytest -q` → **20 passed** (offline).
- `python3 -m bioscientist_os --help` / `info` / `env-check` → all run.
- `biosci --help` → installed console script runs.
- `python3 scripts/00_check_environment.py` → identical report to `biosci env-check`.
- `ruff check src/ tests/test_cli_smoke.py tests/test_package_import.py` → clean.

## Test status
20 passed. No functional tests yet (no schemas, ingestion, search, extraction,
evidence, connectors, visualization, evaluation, or memo code exists). The
subpackages are intentionally empty.

## Known limitations
- This milestone adds only the package skeleton and a descriptive CLI. The
  `biosci` data subcommands listed in `docs/PLAN.md` (`ingest`, `search`,
  `evidence`, `memo`, `eval`, …) do **not** exist yet and would error if invoked.
- `env-check` reports the `sqlite3` *CLI* as "not found"; storage will use
  Python's stdlib `sqlite3` *module* (always present), not the CLI binary.
- A pre-existing line-length lint warning remains in
  `tests/test_repo_contract.py` (out of scope for M0); the new M0 files are
  ruff-clean.

## Possible misleading artifacts
- **The CLI looks more capable than it is.** `biosci info` prints a rich
  description of the full pipeline, but only `version`, `info`, and `env-check`
  are implemented. The `info` text and the website both label this as the
  Milestone-0 skeleton, but a reader skimming `info` could over-read it.
- **A green `env-check` ("RESULT: OK") only means the host can build/test** — it
  says nothing about pipeline correctness or biological validity.
- **20 passing tests** are contract/import/CLI-smoke tests; they assert structure
  and wiring, not any scientific result. No evidence, claim, or metric is
  produced yet.
- The website Milestones page now shows M0 as *Done* while every other milestone
  is *Planned*; "Done" here means the skeleton/CLI exists, not that any research
  capability does.

## Human feedback
<!-- Human will fill this later. -->
