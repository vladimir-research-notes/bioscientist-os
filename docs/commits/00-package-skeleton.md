# Commit note: Milestone 0 — Add bioscientist-os package skeleton and CLI

## Intent
Make the project contract executable: convert the repository from a
docs-and-website scaffold into an importable, testable Python package with a
runnable CLI, without adding any domain logic.

## What the commit contains
- `src/bioscientist_os/`: `__init__.py` (import-light metadata + the four
  epistemic levels + the non-clinical safety note), `cli.py` (`typer` app with
  `version` / `info` / `env-check`), `__main__.py` (`python -m bioscientist_os`),
  `environment.py` (canonical offline env report), and seven empty-but-importable
  subpackages.
- `scripts/00_check_environment.py` rewritten as a thin wrapper over
  `bioscientist_os.environment` (one implementation, two entry points).
- `tests/test_package_import.py` and `tests/test_cli_smoke.py` (12 new tests;
  20 total, all offline).
- Website + docs updates: Milestones page (M0 → Done), Overview and Architecture
  status tables, and `docs/RESULTS.md` build/test status.
- Removed `src/bioscientist_os/.gitkeep` (superseded by real package files).

## Why it is safe to commit
CPU-only, offline, no network or paid API. No secrets, caches, virtualenvs,
weights, or large data are staged (`.venv/`, `*.egg-info/`, `__pycache__/`, and
`results/` remain gitignored). Working tree is clean after commit.
