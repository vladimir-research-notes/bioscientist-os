#!/usr/bin/env python3
"""Ingest the committed fixtures into a local SQLite database (Milestone 2).

A thin, install-free wrapper around :func:`bioscientist_os.ingest.ingest_fixtures`
so the end-to-end run in ``docs/REPRODUCIBILITY.md`` has a single command for the
ingestion step. Offline and CPU-only: no network, no paid API, no secrets.

    python3 scripts/01_ingest_fixtures.py
    python3 scripts/01_ingest_fixtures.py --fixtures data/fixtures \
        --db results/raw/bioscientist.db --reset

Defaults match the documented command: it reads ``data/fixtures/`` and writes
``results/raw/bioscientist.db`` (gitignored, reproducible). Re-running is
idempotent; it prints exactly what it wrote, including a content digest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the src/ layout importable without requiring `pip install -e .`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bioscientist_os.ingest import ingest_fixtures  # noqa: E402  (after sys.path setup)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--fixtures",
        default=str(_REPO_ROOT / "data" / "fixtures"),
        help="fixtures root to ingest (default: data/fixtures)",
    )
    parser.add_argument(
        "--db",
        default=str(_REPO_ROOT / "results" / "raw" / "bioscientist.db"),
        help="SQLite database to create/update (default: results/raw/bioscientist.db)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="delete and recreate the database first"
    )
    args = parser.parse_args(argv)

    report = ingest_fixtures(args.fixtures, db_path=args.db, reset=args.reset)
    print(f"Ingested {report.total_records} records -> {report.db_path}")
    print(f"  papers={report.papers} proteins={report.proteins} "
          f"associations={report.associations} questions={report.questions}")
    print(f"  writes: {report.inserted} inserted, {report.updated} updated (idempotent upsert)")
    print(f"  content digest (sha256): {report.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
