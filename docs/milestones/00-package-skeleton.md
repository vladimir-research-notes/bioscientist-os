# Milestone 0 — Package skeleton and runnable contract

## Summary

Turned the project *contract* (plan, docs, website, runner, permission policy)
into *executable code*: `bioscientist-os` is now an importable, testable Python
package with a runnable `biosci` CLI. No domain logic yet — the seven
subpackages are documented, importable skeletons that gain behavior in later
milestones.

## Deliverables

- **`src/bioscientist_os/__init__.py`** — import-light package root. Exposes
  `__version__` (`0.0.0`, kept in sync with `pyproject.toml`), `PACKAGE_NAME`,
  `DESCRIPTION`, `EPISTEMIC_LEVELS` (the four levels with glosses), `SAFETY_NOTE`
  (the non-clinical stance), and `SUBPACKAGES`. Deliberately imports no
  third-party package so the environment check can run before deps are installed.
- **`src/bioscientist_os/cli.py`** — the `biosci` CLI (`typer`) with three
  read-only, offline subcommands: `version`, `info`, and `env-check`. The console
  entry point is `bioscientist_os.cli:main` (see `pyproject.toml`).
- **`src/bioscientist_os/__main__.py`** — routes `python -m bioscientist_os` to
  the same CLI.
- **`src/bioscientist_os/environment.py`** — the canonical offline environment
  report (stdlib-only). It now also checks that the package itself imports.
- **Seven subpackages**, each with a docstring naming its responsibility and
  milestone: `ingest/`, `search/`, `evidence/`, `databases/`, `visualization/`,
  `storage/`, `evals/`.
- **`scripts/00_check_environment.py`** — rewritten as a thin wrapper that puts
  `src/` on `sys.path` and delegates to `bioscientist_os.environment.main`, so the
  script and `biosci env-check` share one implementation.
- **Tests**: `tests/test_package_import.py` (7) and `tests/test_cli_smoke.py` (5),
  alongside the existing `tests/test_repo_contract.py` (8).

## Design notes / decisions

- **Import-light root.** `import bioscientist_os` pulls in no third-party
  dependency. This lets `scripts/00_check_environment.py` import the package and
  report a *missing* core dependency rather than crashing on it — the env check
  must work on a host that has not run `pip install` yet.
- **One environment-check implementation, two entry points.** The logic lives in
  `bioscientist_os.environment`; both the CLI subcommand and the numbered script
  call it. This is the "wire the script to the package" item from the plan, done
  without duplicating the dependency manifest.
- **`env-check` exit code reflects only hard blockers.** Python `< 3.12` or a
  missing *required* core dependency exit non-zero; missing optional extras
  (`matplotlib`, `duckdb`, `anthropic`) are informational PASS lines.
- **`info` surfaces safety up front.** The four epistemic levels and the
  non-clinical disclaimer are printed by `biosci info` and asserted by a test, so
  the safety stance is part of the runnable surface, not just the docs.
- **Version single-sourcing.** A test parses `pyproject.toml` and asserts it
  matches `bioscientist_os.__version__`, so the two cannot silently drift.

## Validation

```bash
python3 -m pytest -q                 # 20 passed (offline)
python3 -m bioscientist_os --help    # shows version / info / env-check
biosci --help                        # installed console script works
python3 -m bioscientist_os info      # identity + 4 epistemic levels + safety note
python3 -m bioscientist_os env-check # RESULT: OK (host can build and test on CPU)
python3 scripts/00_check_environment.py   # identical report via the shared module
ruff check src/ tests/test_cli_smoke.py tests/test_package_import.py   # clean
```

All offline; no network, no paid API, no GPU.

## Status

**Complete.** Next: **Milestone 1 — Data schemas and small fixtures** (typed
`pydantic` models with provenance fields, plus small clearly-labeled fixtures on
the cellular-senescence / longevity / autophagy theme).
