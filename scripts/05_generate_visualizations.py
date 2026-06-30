#!/usr/bin/env python3
"""Generate the workbench figures from the ingested corpus (Milestone 7).

A thin, install-free wrapper around :mod:`bioscientist_os.visualization`. It reads
the ingested SQLite database, builds the five figures' inspectable *data* from the
workbench's own reports (M3 topics, M4 extraction, M5 evidence tables), writes that
data as ``results/figures/visualizations.json``, and — when the optional
``matplotlib`` extra is installed — renders the PNGs alongside it.

Artifacts written under ``results/figures/`` (gitignored):

* ``visualizations.json``   — the data behind every figure (always written);
* ``timeline.png``          — papers per publication year;
* ``topic_clusters.png``    — the M3 single-link cosine topic groups;
* ``evidence_matrix.png``   — papers x question entities, support/conflict/unknown;
* ``link_graph.png``        — entity / database-link graph;
* ``support_conflict.png``  — support-vs-conflict table per research question.

Offline and CPU-only: no network, no paid API, no secrets. The figure *data* is
deterministic, so re-running reproduces ``visualizations.json`` exactly (PNG bytes
may vary by matplotlib version). If matplotlib is absent, the PNGs are skipped and
the script says so — the JSON is still written, keeping the chain inspectable.

    python3 scripts/05_generate_visualizations.py
    python3 scripts/05_generate_visualizations.py --db results/raw/bioscientist.db \
        --out-dir results/figures
    python3 scripts/05_generate_visualizations.py --no-render   # data only

Reminder: the evidence-matrix support/conflict/unknown cells and the link-graph
database edges are heuristic / inferred respectively, not biological or clinical
verdicts (see docs/SAFETY.md).
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

from bioscientist_os.search import DEFAULT_THRESHOLD  # noqa: E402
from bioscientist_os.visualization import (  # noqa: E402
    load_visualizations,
    write_visualizations,
)


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
        default=str(_REPO_ROOT / "results" / "figures"),
        help="directory for visualizations.json and the PNGs (default: results/figures)",
    )
    parser.add_argument(
        "--question", default=None, help="research question (text or stored id) for the matrix"
    )
    parser.add_argument(
        "--question-id", default=None, help="select the evidence-matrix question by stored id"
    )
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"topic-cluster cosine threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--no-render", action="store_true", help="write the figure data only; never render PNGs"
    )
    args = parser.parse_args(argv)

    try:
        report = load_visualizations(
            args.db,
            question_text=args.question,
            question_id=args.question_id,
            threshold=args.threshold,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: run  python3 scripts/01_ingest_fixtures.py  to create {args.db}",
              file=sys.stderr)
        return 1
    except KeyError:
        print(f"error: no stored question with id {args.question_id!r}", file=sys.stderr)
        return 1

    tl, cl, mx = report.timeline, report.clusters, report.matrix
    lg, totals = report.link_graph, report.support_table.totals()
    print(f"Built figures from {args.db}  (data_source={report.data_source})")
    print(f"  timeline        : {tl.total_papers} papers across {tl.num_years} years"
          + (f" ({tl.undated} undated)" if tl.undated else ""))
    print(f"  topic clusters  : {cl.num_groups} groups ({cl.num_singletons} singleton) "
          f"at threshold {cl.threshold}")
    print(f"  evidence matrix : {mx.question_id} — {mx.shape[0]} papers x {mx.shape[1]} "
          f"entities ({mx.num_rows_used} claim rows); cells {mx.cell_counts()}")
    print(f"  link graph      : {len(lg.nodes)} nodes, {len(lg.edges)} edges "
          f"(nodes {lg.node_counts()}; edges {lg.edge_counts()})")
    print(f"  support table   : {len(report.support_table.rows)} questions — "
          f"support={totals['support']} conflict={totals['conflict']} unknown={totals['unknown']}")

    out_dir = Path(args.out_dir)
    artifacts = write_visualizations(report, out_dir, render=not args.no_render)

    print()
    print(f"Wrote {artifacts.json_path}")
    if artifacts.rendered:
        for key in report.FIGURE_KEYS:
            print(f"Wrote {artifacts.figure_paths[key]}")
    elif args.no_render:
        print("(--no-render: PNGs skipped; figure data written to JSON only)")
    else:
        print("(matplotlib not installed: PNGs skipped; install with  pip install -e '.[viz]'  "
              "— figure data was written to JSON)")
    print("(matrix support/conflict/unknown is a heuristic textual signal; link-graph "
          "database edges are inferred relations — neither is a biological/clinical verdict)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
