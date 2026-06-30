#!/usr/bin/env python3
"""Extract entities and claims from the ingested corpus (Milestone 4).

A thin, install-free wrapper around :mod:`bioscientist_os.evidence`. It reads the
ingested SQLite database, builds the fixture-built entity dictionary, runs the
rule-based entity/claim extraction, prints a summary, and writes three inspectable,
regenerable artifacts under ``results/processed/`` (gitignored):

* ``claims.json``   — the full extraction report (entities + claims per paper);
* ``claims.csv``    — one row per extracted claim, with provenance and span;
* ``entities.csv``  — one row per recognized entity, with provenance and span.

Offline and CPU-only: no network, no paid API, no secrets. Extraction is
deterministic, so re-running reproduces the artifacts exactly.

    python3 scripts/03_extract_claims.py
    python3 scripts/03_extract_claims.py --db results/raw/bioscientist.db \
        --out-dir results/processed
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

from bioscientist_os.evidence import load_extraction  # noqa: E402  (after sys.path setup)
from bioscientist_os.evidence.model import ExtractionReport  # noqa: E402


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


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
        help="directory for claims.json / claims.csv / entities.csv "
        "(default: results/processed)",
    )
    args = parser.parse_args(argv)

    try:
        report = load_extraction(args.db)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: run  python3 scripts/01_ingest_fixtures.py  to create {args.db}",
              file=sys.stderr)
        return 1

    print(f"Extracted from {report.total_papers} papers in {args.db}")
    print(f"  dictionary           : {report.params['dictionary_entities']} entities / "
          f"{report.params['dictionary_surfaces']} surfaces")
    print(f"  entity mentions      : {report.num_entities}")
    print(f"  claims               : {report.num_claims}")
    print(f"  relation triples     : {report.num_relations} "
          f"(of {report.num_claims} claims)")
    print(f"  data_source          : {report.data_source}")
    print()
    print("Sample relation triples (read from sentences, not inferred):")
    shown = 0
    for c in report.all_claims:
        if c.relation and shown < 8:
            print(f"  {c.paper_id}: {c.subject} --{c.relation}--> {c.object}")
            shown += 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    claims_json = out_dir / "claims.json"
    claims_csv = out_dir / "claims.csv"
    entities_csv = out_dir / "entities.csv"

    claims_json.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_csv(claims_csv, ExtractionReport.CLAIM_COLUMNS, report.claim_rows())
    _write_csv(entities_csv, ExtractionReport.ENTITY_COLUMNS, report.entity_rows())

    print()
    print(f"Wrote {claims_json}")
    print(f"Wrote {claims_csv}  ({report.num_claims} rows)")
    print(f"Wrote {entities_csv}  ({report.num_entities} rows)")
    print("(entities are observed metadata; claims are extracted claims; every row "
          "carries paper_id, exact span, method — no biological claim is made)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
