#!/usr/bin/env python3
"""Build the in-memory search index and topic grouping over the corpus (Milestone 3).

A thin, install-free wrapper around :mod:`bioscientist_os.search`. It reads the
ingested SQLite database, builds the field-aware index, prints corpus statistics
and the topic grouping, optionally runs demo queries, and writes an inspectable
JSON summary to ``results/processed/search_index.json`` (gitignored, regenerable).
Offline and CPU-only: no network, no paid API, no secrets.

    python3 scripts/02_build_index.py
    python3 scripts/02_build_index.py --db results/raw/bioscientist.db \
        --query "cellular senescence inflammation" --query "autophagy mTOR" \
        --threshold 0.15

The search index is recomputed in memory from the database each run (appropriate
for the small corpora this workbench targets); the JSON summary is an artifact for
inspection, not a persisted inverted index. Re-running is deterministic.
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

from bioscientist_os.search import group_topics, load_index  # noqa: E402  (after sys.path setup)
from bioscientist_os.search.topics import DEFAULT_THRESHOLD  # noqa: E402


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
        default=str(_REPO_ROOT / "results" / "processed" / "search_index.json"),
        help="JSON summary to write (default: results/processed/search_index.json)",
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"topic cosine threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--query", action="append", default=[],
        help="demo query to run (repeatable)",
    )
    parser.add_argument("--limit", type=int, default=5, help="hits per demo query (default: 5)")
    args = parser.parse_args(argv)

    try:
        index = load_index(args.db)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: run  python3 scripts/01_ingest_fixtures.py  to create {args.db}",
              file=sys.stderr)
        return 1

    stats = index.corpus_stats()
    report = group_topics(index, threshold=args.threshold)

    print(f"Indexed {stats['num_papers']} papers from {args.db}")
    print(f"  vocabulary           : {stats['vocabulary_size']} distinct terms")
    print(f"  avg field length     : {stats['avg_field_length']}")
    print(f"  field weights (BM25F): {stats['field_weights']}")
    print(f"  data_source          : {stats['data_source']}")
    print()
    print(f"Topics (threshold={report.threshold}): {report.num_groups} groups "
          f"({report.num_singletons} singleton)")
    for g in report.groups:
        print(f"  {g.topic_id} (n={g.size}): {', '.join(g.label_terms)}")

    demo = []
    for q in args.query:
        response = index.search(q, limit=args.limit)
        demo.append(response.to_dict())
        print()
        print(f'Query "{q}" -> {len(response.hits)} hits')
        for hit in response.hits:
            print(f"  {hit.rank}. {hit.score:.3f}  {hit.paper_id}  {hit.title}")
            print(f"        matched: {hit.why()}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "db": str(args.db),
        "corpus_stats": stats,
        "topics": report.to_dict(),
        "demo_queries": demo,
    }
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print()
    print(f"Wrote search-index summary -> {out_path}")
    print("(in-memory index; results are observed-metadata rankings/groupings, not claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
