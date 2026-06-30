#!/usr/bin/env python3
"""Run the workbench self-evaluation against committed gold labels (Milestone 8).

A thin, install-free wrapper around :mod:`bioscientist_os.evals`. It reads the
ingested SQLite database and the committed gold labels under
``data/fixtures/gold/``, scores the pipeline (ingestion correctness, BM25F search
recall on labeled queries, dictionary entity precision/recall, claim-extraction
sanity, evidence-table completeness, and provenance coverage), prints a
denominator-first text summary, and writes the full report as JSON.

Artifact written under ``results/processed/`` (gitignored):

* ``eval_report.json`` — every metric with its numerator/denominator and a 95%
  Wilson interval, plus the per-query / per-abstract / per-question breakdowns.

Offline and CPU-only: no network, no paid API, no secrets. The evaluators are pure
functions over the corpus + gold labels, so re-running reproduces the report
exactly.

    python3 scripts/06_run_eval.py
    python3 scripts/06_run_eval.py --db results/raw/bioscientist.db \
        --out results/processed/eval_report.json
    python3 scripts/06_run_eval.py --confidence 0.9 --recall-k 1 --recall-k 5

Reminder: this evaluates the PIPELINE on a tiny, partly-synthetic fixture corpus —
not biological truth. Small N means wide intervals (see docs/SAFETY.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the src/ layout importable without requiring `pip install -e .`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bioscientist_os.evals import DEFAULT_RECALL_K, run_eval  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db",
        default=str(_REPO_ROOT / "results" / "raw" / "bioscientist.db"),
        help="ingested SQLite database (default: results/raw/bioscientist.db)",
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "results" / "processed" / "eval_report.json"),
        help="path for the JSON report (default: results/processed/eval_report.json)",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.95,
        help="confidence level for the Wilson intervals (default: 0.95)",
    )
    parser.add_argument(
        "--recall-k", type=int, action="append", default=None,
        help="recall@k cut-off; repeatable (default: 3 and 5)",
    )
    args = parser.parse_args(argv)

    if not 0.0 < args.confidence < 1.0:
        print("error: --confidence must be in (0, 1)", file=sys.stderr)
        return 2
    ks = tuple(args.recall_k) if args.recall_k else DEFAULT_RECALL_K

    try:
        report = run_eval(args.db, confidence=args.confidence, recall_k=ks)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: run  python3 scripts/01_ingest_fixtures.py  to create {args.db}",
              file=sys.stderr)
        return 1

    print(report.format_text())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    print()
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
