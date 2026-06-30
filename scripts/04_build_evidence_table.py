#!/usr/bin/env python3
"""Build evidence tables from the ingested corpus (Milestone 5).

A thin, install-free wrapper around :mod:`bioscientist_os.evidence`. It reads the
ingested SQLite database, builds the fixture entity dictionary, extracts the corpus,
and assembles an evidence table for each stored research question (or one passed
with ``--question`` / ``--question-id``). Every row carries provenance, database
links, and a heuristic support/conflict/unknown label.

Artifacts written under ``results/processed/`` (gitignored):

* ``evidence_<question_id>.csv`` — one CSV per stored research question;
* ``evidence_table.csv``         — a copy of the first table, matching the
  ``docs/PLAN.md`` example command's output name;
* ``evidence_tables.json``       — every table's full JSON (question, params,
  support counts, provenance coverage, rows).

Offline and CPU-only: no network, no paid API, no secrets. Assembly is
deterministic, so re-running reproduces the artifacts exactly.

    python3 scripts/04_build_evidence_table.py
    python3 scripts/04_build_evidence_table.py --db results/raw/bioscientist.db \
        --out-dir results/processed
    python3 scripts/04_build_evidence_table.py \
        --question "What evidence links cellular senescence to chronic inflammation?"

Reminder: support/conflict/unknown is a heuristic *textual* signal, not a
biological or clinical verdict (see docs/SAFETY.md).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Make the src/ layout importable without requiring `pip install -e .`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bioscientist_os.evidence import EvidenceReport, load_evidence  # noqa: E402
from bioscientist_os.storage import SQLiteStore  # noqa: E402


def _write_csv(path: Path, report: EvidenceReport) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(EvidenceReport.EVIDENCE_COLUMNS))
        writer.writeheader()
        writer.writerows(report.evidence_rows())


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
        "--out-dir",
        default=str(_REPO_ROOT / "results" / "processed"),
        help="directory for the CSV/JSON artifacts (default: results/processed)",
    )
    parser.add_argument(
        "--question", default=None, help="build for one question text instead of all stored ones"
    )
    parser.add_argument(
        "--question-id", default=None, help="build for one stored question id"
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.0, help="drop claims below this confidence"
    )
    args = parser.parse_args(argv)

    # Decide which questions to build for.
    try:
        with SQLiteStore(args.db) as store:
            if not store.is_initialized():
                raise ValueError(
                    f"{args.db} is not a bioscientist-os database (no ingested tables)"
                )
            stored_ids = [q.question_id for q in store.iter_research_questions()]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: run  python3 scripts/01_ingest_fixtures.py  to create {args.db}",
              file=sys.stderr)
        return 1

    if args.question is not None or args.question_id is not None:
        targets: list[dict] = [{"question_text": args.question, "question_id": args.question_id}]
    else:
        targets = [{"question_id": qid} for qid in stored_ids]
    if not targets:
        print("no research questions to build for", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[EvidenceReport] = []
    for spec in targets:
        try:
            report = load_evidence(args.db, min_confidence=args.min_confidence, **spec)
        except KeyError:
            print(f"error: no stored question with id {spec.get('question_id')!r}", file=sys.stderr)
            return 1
        reports.append(report)

    print(f"Built {len(reports)} evidence table(s) from {args.db}")
    for report in reports:
        counts = report.support_counts()
        qid = report.question.question_id
        csv_path = out_dir / f"evidence_{qid}.csv"
        _write_csv(csv_path, report)
        print(
            f"  {qid:<28} rows={report.num_rows:>3}  "
            f"support={counts['support']:>2} conflict={counts['conflict']:>2} "
            f"unknown={counts['unknown']:>2}  "
            f"provenance={report.provenance_coverage:.0%}  -> {csv_path.name}"
        )

    # A copy of the first table under the PLAN example's name.
    primary_csv = out_dir / "evidence_table.csv"
    _write_csv(primary_csv, reports[0])

    json_path = out_dir / "evidence_tables.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, sort_keys=True), encoding="utf-8"
    )

    print()
    print(f"Wrote {primary_csv}  (copy of {reports[0].question.question_id})")
    print(f"Wrote {json_path}  ({len(reports)} tables)")
    print("(every row carries paper_id, exact span, and method; support/conflict/unknown "
          "is a heuristic textual signal, not a biological or clinical verdict)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
