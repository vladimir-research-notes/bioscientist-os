#!/usr/bin/env python3
"""Generate end-to-end research memos from the ingested corpus (Milestone 9).

A thin, install-free wrapper around :mod:`bioscientist_os.evidence.memo`. It reads
the ingested SQLite database and assembles a structured research memo for each
stored research question (or one passed with ``--question`` / ``--question-id``).
Each memo composes the workbench's transparent layers — BM25F key papers, the M5
evidence table, UniProt/HGNC + Open Targets database links, textual-conflict rows
and candidate cross-paper disagreements — and suggests next experiments *only* as
explicitly **unsupported hypotheses**. The four epistemic levels are kept separate
and every evidence row carries full provenance.

Artifacts written under ``results/processed/`` (gitignored):

* ``memo_<question_id>.md`` — one Markdown memo per stored research question;
* ``memo.md``               — a copy of the first memo, matching the
  ``docs/PLAN.md`` example command's output name;
* ``memos.json``            — every memo's full structured JSON.

Offline and CPU-only: no network, no paid API, no secrets. Assembly is
deterministic, so re-running reproduces the artifacts exactly.

    python3 scripts/07_generate_memo.py
    python3 scripts/07_generate_memo.py --db results/raw/bioscientist.db \
        --out-dir results/processed
    python3 scripts/07_generate_memo.py \
        --question "What evidence links cellular senescence to chronic inflammation?"

Reminder: this is a research-assistance artifact, NOT medical, diagnostic, or
treatment advice. Suggested experiments are unsupported hypotheses for a human to
evaluate, never recommendations (see docs/SAFETY.md).
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

from bioscientist_os.evidence import load_memo  # noqa: E402
from bioscientist_os.storage import SQLiteStore  # noqa: E402


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
        help="directory for the Markdown/JSON artifacts (default: results/processed)",
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
    parser.add_argument(
        "--max-papers", type=int, default=8, help="maximum key papers to list (default: 8)"
    )
    parser.add_argument(
        "--max-hypotheses", type=int, default=6,
        help="maximum unsupported hypotheses to suggest (default: 6)",
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

    reports = []
    for spec in targets:
        try:
            report = load_memo(
                args.db,
                min_confidence=args.min_confidence,
                max_papers=args.max_papers,
                max_hypotheses=args.max_hypotheses,
                **spec,
            )
        except KeyError:
            print(f"error: no stored question with id {spec.get('question_id')!r}", file=sys.stderr)
            return 1
        reports.append(report)

    print(f"Built {len(reports)} research memo(s) from {args.db}")
    for report in reports:
        counts = report.support_counts
        qid = report.question.question_id
        md_path = out_dir / f"memo_{qid}.md"
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        print(
            f"  {qid:<28} rows={report.num_rows:>3}  "
            f"support={counts['support']:>2} conflict={counts['conflict']:>2} "
            f"unknown={counts['unknown']:>2}  "
            f"key_papers={len(report.key_papers)}  "
            f"hypotheses={len(report.hypotheses)}  -> {md_path.name}"
        )

    # A copy of the first memo under the PLAN example's name.
    primary_md = out_dir / "memo.md"
    primary_md.write_text(reports[0].to_markdown(), encoding="utf-8")

    json_path = out_dir / "memos.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, sort_keys=True), encoding="utf-8"
    )

    print()
    print(f"Wrote {primary_md}  (copy of {reports[0].question.question_id})")
    print(f"Wrote {json_path}  ({len(reports)} memos)")
    print("(suggested experiments are UNSUPPORTED hypotheses for a human to evaluate, "
          "never recommendations or clinical advice — see docs/SAFETY.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
