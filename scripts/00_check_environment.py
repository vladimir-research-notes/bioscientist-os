#!/usr/bin/env python3
"""Offline environment report for bioscientist-os.

Thin wrapper around the canonical implementation in
``bioscientist_os.environment`` so this script and the ``biosci env-check``
subcommand share one code path and never drift. Stdlib-only and offline: it makes
no network calls, installs nothing, and reads no secrets.

To run from a clean checkout without an editable install, it prepends the repo's
``src/`` directory to ``sys.path`` (the same trick ``conftest.py`` uses for
tests).

    python3 scripts/00_check_environment.py
    python3 scripts/00_check_environment.py --json

Exit status is non-zero only on a hard blocker (e.g. Python older than 3.12 or a
missing required core dependency). Missing optional packages are reported as
INFO, not failures.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src/ layout importable without requiring `pip install -e .`.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bioscientist_os.environment import main  # noqa: E402  (after sys.path setup)

if __name__ == "__main__":
    raise SystemExit(main())
