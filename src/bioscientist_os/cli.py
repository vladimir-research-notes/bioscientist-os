"""The ``biosci`` command-line interface.

Milestone 0 ships three read-only, offline subcommands that describe the tool and
check the host:

* ``biosci version``    — print the package version;
* ``biosci info``       — print identity, the four epistemic levels, and the
                          non-clinical safety stance;
* ``biosci env-check``  — report whether this host can build and test on CPU
                          (delegates to :mod:`bioscientist_os.environment`).

Milestone 2 adds the local-data subcommands:

* ``biosci ingest <dir> --db <path>`` — load fixtures into a SQLite database;
* ``biosci stats --db <path>``        — report what an ingested database contains.

Milestone 3 adds CPU-only search and topic grouping over the ingested corpus:

* ``biosci search "<query>" --db <path>`` — BM25F lexical search with a per-term,
  per-field score explanation (optional TF-IDF cosine mode);
* ``biosci topics --db <path>``           — single-link cosine topic grouping.

Milestone 4 adds the transparent, non-LLM extraction baseline:

* ``biosci extract --db <path>`` — dictionary entity recognition plus claim-sentence
  extraction (with optional subject–relation–object triples), each carrying a
  confidence and full provenance (paper, exact snippet span, method).

Milestone 5 assembles the headline artifact, the evidence table:

* ``biosci evidence --question "<text>" --db <path> [--out <csv>]`` — group the
  extracted claims by a research question into a table whose every row carries
  provenance, database links, and a heuristic support/conflict/unknown label.

Later milestones add the remaining data subcommands defined in ``docs/PLAN.md``
(``eval``, ``memo``). The console entry point is
``bioscientist_os.cli:main`` (see ``pyproject.toml``); ``python -m bioscientist_os``
routes here too via ``__main__``.
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import typer

from bioscientist_os import (
    DESCRIPTION,
    EPISTEMIC_LEVELS,
    PACKAGE_NAME,
    SAFETY_NOTE,
    __version__,
)

app = typer.Typer(
    name="biosci",
    add_completion=False,
    no_args_is_help=True,
    help=(
        "bioscientist-os — CPU-first, evidence-centered biomedical research "
        "workbench. Research-assistance only; NOT a medical-advice or diagnostic "
        "tool (see docs/SAFETY.md)."
    ),
)


@app.command()
def version() -> None:
    """Print the package version and exit."""
    typer.echo(__version__)


@app.command()
def info() -> None:
    """Print package identity, the four epistemic levels, and the safety stance."""
    lines = [
        f"{PACKAGE_NAME} {__version__}",
        "",
        DESCRIPTION,
        "",
        "Provenance is a first-class field: every claim, link, and evidence-table",
        "cell records paper_id, source_snippet, extraction_method, and data_source",
        "(fixture / cache / live).",
        "",
        "Every output separates four epistemic levels and never collapses them:",
    ]
    for i, (level, gloss) in enumerate(EPISTEMIC_LEVELS, start=1):
        lines.append(f"  {i}. {level:<22} — {gloss}")
    lines += [
        "",
        f"Safety: {SAFETY_NOTE}",
        "",
        "Status: fixture ingestion, local SQLite storage, CPU-only search + topic "
        "grouping, rule-based entity/claim extraction, and evidence-table assembly "
        "available (Milestones 0-5).",
        "Evaluation and memo subcommands land milestone by milestone — see "
        "docs/PLAN.md and the website Milestones page.",
    ]
    typer.echo("\n".join(lines))


@app.command("env-check")
def env_check(
    json_output: bool = typer.Option(
        False, "--json", help="emit the report as JSON instead of text"
    ),
) -> None:
    """Report whether this host can build and test the workbench on CPU (offline).

    Exits non-zero only on a hard blocker (Python < 3.12, or a missing *required*
    core dependency); missing optional extras are informational.
    """
    # Imported lazily so the rest of the CLI does not pay for it, and so the
    # module stays stdlib-only and independently runnable.
    from bioscientist_os import environment

    report = environment.run_checks()
    if json_output:
        typer.echo(_json.dumps(environment.report_payload(report), indent=2))
    else:
        typer.echo(environment.format_text(report))
    raise typer.Exit(code=0 if report.hard_ok else 1)


@app.command()
def ingest(
    fixtures_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="fixtures root to ingest, e.g. data/fixtures",
    ),
    db: Path = typer.Option(
        ..., "--db", help="SQLite database to create or update, e.g. results/raw/bioscientist.db"
    ),
    reset: bool = typer.Option(
        False, "--reset", help="delete and recreate the database before ingesting"
    ),
) -> None:
    """Load the fixture corpus into a local SQLite database (offline, deterministic).

    Writes are idempotent: re-running over the same fixtures updates rows in place
    and creates no duplicates. Every ingested row is *observed metadata* with
    ``data_source = fixture``; no claims or relations are produced here.
    """
    from bioscientist_os.ingest import ingest_fixtures

    report = ingest_fixtures(fixtures_dir, db_path=db, reset=reset)
    lines = [
        f"Ingested {report.total_records} records from {fixtures_dir} -> {report.db_path}",
        f"  papers       : {report.papers}",
        f"  proteins     : {report.proteins}  (UniProt-style)",
        f"  associations : {report.associations}  (Open Targets-style)",
        f"  questions    : {report.questions}",
        f"  writes       : {report.inserted} inserted, {report.updated} updated (idempotent)",
        f"  content digest (sha256): {report.digest}",
        "",
        "All rows are level: observed metadata (data_source=fixture). "
        "Inspect with: biosci stats --db " + str(report.db_path),
    ]
    typer.echo("\n".join(lines))


@app.command()
def stats(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to summarize"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the summary as JSON instead of text"
    ),
) -> None:
    """Report what an ingested database contains (counts, breakdown, digest)."""
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db) as store:
        if not store.is_initialized():
            typer.echo(
                f"{db} is not a bioscientist-os database (no ingested tables). "
                "Run: biosci ingest data/fixtures --db " + str(db),
                err=True,
            )
            raise typer.Exit(code=1)
        counts = store.table_counts()
        breakdown = store.record_breakdown()
        meta = store.meta()
        digest = store.content_digest()

    if json_output:
        payload = {
            "db": str(db),
            "counts": counts,
            "database_records_by_source": [
                {"source": s, "record_type": t, "count": n} for s, t, n in breakdown
            ],
            "meta": meta,
            "content_digest": digest,
        }
        typer.echo(_json.dumps(payload, indent=2, sort_keys=True))
        return

    lines = [
        f"Database: {db}",
        f"  papers             : {counts['papers']}",
        f"  database records   : {counts['database_records']}",
    ]
    for source, record_type, n in breakdown:
        lines.append(f"      {source}/{record_type}: {n}")
    lines += [
        f"  research questions : {counts['research_questions']}",
        f"  schema version     : {meta.get('schema_version', '?')}",
        f"  content digest     : {digest}",
        "",
        "All rows are level: observed metadata (data_source=fixture). "
        "Not a clinical or diagnostic data source (see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


def _load_index_or_exit(db: Path):
    """Open ``db`` and build a search index, or print the ``stats``-style error and exit 1."""
    from bioscientist_os.search import load_index

    try:
        return load_index(db)
    except ValueError:
        typer.echo(
            f"{db} is not a bioscientist-os database (no ingested tables). "
            "Run: biosci ingest data/fixtures --db " + str(db),
            err=True,
        )
        raise typer.Exit(code=1) from None


@app.command()
def search(
    query: str = typer.Argument(..., help='search query, e.g. "cellular senescence inflammation"'),
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to search"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="maximum hits to return"),
    method: str = typer.Option(
        "bm25", "--method", help="scoring method: 'bm25' (default) or 'tfidf' (cosine)"
    ),
    explain: bool = typer.Option(
        False, "--explain", help="show the full per-term score breakdown for each hit"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the result as JSON instead of text"
    ),
) -> None:
    """Search the ingested corpus (CPU-only, offline) with a transparent lexical baseline.

    Default scoring is BM25F over the title / keywords / abstract fields; every hit
    carries which query terms matched, in which fields, and each term's score
    contribution. Results are a *ranking of observed-metadata papers* — search makes
    no claims and asserts no biology.
    """
    index = _load_index_or_exit(db)
    if method not in ("bm25", "tfidf"):
        typer.echo(f"unknown --method {method!r}; use 'bm25' or 'tfidf'", err=True)
        raise typer.Exit(code=2)
    response = index.search(query, limit=limit) if method == "bm25" else index.tfidf_search(
        query, limit=limit
    )

    if json_output:
        typer.echo(_json.dumps(response.to_dict(), indent=2, sort_keys=True))
        return

    header = (
        f'Search: "{response.query}"  (method={response.method}, '
        f"N={response.total_papers}, data_source={response.data_source})"
    )
    lines = [header, "query terms: " + (", ".join(response.query_terms) or "(none)")]
    if not response.hits:
        lines.append("  (no matching papers)")
    for hit in response.hits:
        year = hit.year if hit.year is not None else "----"
        lines.append(f"  {hit.rank:>2}. {hit.score:7.3f}  {hit.paper_id}  {year}  {hit.title}")
        lines.append(f"        matched: {hit.why()}")
        if explain:
            for m in hit.term_matches:
                fields = ", ".join(f"{f}:{n}" for f, n in sorted(m.field_tf.items())) or "—"
                lines.append(
                    f"          {m.term:<18} idf={m.idf:6.3f}  fields[{fields}]  "
                    f"wtf={m.weighted_tf:6.3f}  +{m.contribution:6.3f}"
                )
    lines += [
        "",
        "Hits are observed metadata (ranked papers); search produces no claims or "
        "relations (see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


@app.command()
def topics(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to group"
    ),
    threshold: float = typer.Option(
        None, "--threshold", help="cosine edge threshold (default: the documented baseline)"
    ),
    top_terms: int = typer.Option(6, "--top-terms", help="label terms to show per group"),
    json_output: bool = typer.Option(
        False, "--json", help="emit the report as JSON instead of text"
    ),
) -> None:
    """Group the corpus into topics by single-link cosine clustering (transparent baseline).

    Connected components of a TF-IDF cosine-similarity graph; each group is labeled
    by its most distinctive terms. Groups describe papers — they are not asserted
    topics of the field.
    """
    from bioscientist_os.search import DEFAULT_THRESHOLD, group_topics

    index = _load_index_or_exit(db)
    report = group_topics(
        index, threshold=DEFAULT_THRESHOLD if threshold is None else threshold, top_terms=top_terms
    )

    if json_output:
        typer.echo(_json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    lines = [
        f"Topic report  (method={report.method})",
        f"  threshold={report.threshold}  N={report.total_papers}  "
        f"groups={report.num_groups} ({report.num_singletons} singleton)  "
        f"data_source={report.data_source}",
        "",
    ]
    for g in report.groups:
        lines.append(f"  {g.topic_id}  (n={g.size})  terms: {', '.join(g.label_terms)}")
        for pid in g.paper_ids:
            lines.append(f"        {pid}")
    lines += [
        "",
        "Groups are a transparent clustering of observed-metadata papers; the labels "
        "describe a group, they are not claims (see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


def _load_extraction_or_exit(db: Path):
    """Build the dictionary and extract the corpus, or print the error and exit 1."""
    from bioscientist_os.evidence import load_extraction

    try:
        return load_extraction(db)
    except ValueError:
        typer.echo(
            f"{db} is not a bioscientist-os database (no ingested tables). "
            "Run: biosci ingest data/fixtures --db " + str(db),
            err=True,
        )
        raise typer.Exit(code=1) from None


@app.command()
def extract(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to extract from"
    ),
    paper: str = typer.Option(
        None, "--paper", help="restrict output to one paper_id (default: all papers)"
    ),
    min_confidence: float = typer.Option(
        0.0, "--min-confidence", help="only show claims with confidence >= this value"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the full extraction as JSON instead of text"
    ),
) -> None:
    """Recognize entities and extract claims from abstracts (transparent, non-LLM baseline).

    Entities are dictionary matches (``dict:exact``) at level *observed metadata*;
    claims are entity-grounded abstract sentences (level *extracted claim*) with an
    optional subject–relation–object triple. Every result carries a confidence and
    full provenance (paper, exact source-snippet span, method). No support/conflict
    judgement and no biological assertion is made here (that is the evidence table,
    M5; see docs/SAFETY.md).
    """
    report = _load_extraction_or_exit(db)

    if json_output:
        typer.echo(_json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    selected = [p for p in report.papers if paper in (None, p.paper_id)]
    if paper is not None and not selected:
        typer.echo(f"no paper with paper_id {paper!r} in {db}", err=True)
        raise typer.Exit(code=1)

    lines = [
        f"Extraction  (method={report.method})",
        f"  N={report.total_papers} papers  data_source={report.data_source}  "
        f"dictionary={report.params['dictionary_entities']} entities / "
        f"{report.params['dictionary_surfaces']} surfaces",
        f"  totals: {report.num_entities} entity mentions, {report.num_claims} claims, "
        f"{report.num_relations} relation triples"
        + (f"  (claims filtered to confidence >= {min_confidence})" if min_confidence > 0 else ""),
        "",
    ]
    for pe in selected:
        claims = [c for c in pe.claims if c.confidence >= min_confidence]
        lines.append(f"{pe.paper_id}  {pe.title}")
        lines.append("  entities:")
        if not pe.entities:
            lines.append("      (none recognized)")
        for e in pe.entities:
            xrefs = ", ".join(f"{k}:{v}" for k, v in sorted(e.db_xrefs.items())) or "—"
            span = e.provenance.char_span
            lines.append(
                f"      {e.entity_id:<34} {e.entity_type.value:<8} [{xrefs}]  "
                f"conf={e.confidence:.2f}  snippet={e.provenance.source_snippet!r}@{list(span)}"
            )
        lines.append("  claims:")
        if not claims:
            lines.append("      (none)")
        for c in claims:
            if c.relation:
                triple = f"  {c.subject} --{c.relation}--> {c.object}"
            else:
                triple = ""
            lines.append(
                f"      [{c.claim_id}] conf={c.confidence:.2f} "
                f"{c.provenance.extraction_method}{triple}"
            )
            lines.append(f"          {c.claim_text!r} @{list(c.provenance.char_span)}")
            lines.append(f"          entities: {', '.join(c.entity_ids) or '—'}")
        lines.append("")
    lines += [
        "Entities are observed metadata (recognized mentions); claims are extracted "
        "claims read from abstracts.",
        "Relation triples are read from the sentence, not inferred; no support/conflict "
        "or biological claim is made here (see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


@app.command()
def evidence(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to build from"
    ),
    question: str = typer.Option(
        None,
        "--question",
        "-q",
        help='research question text (or a stored question id), '
        'e.g. "What evidence links cellular senescence to chronic inflammation?"',
    ),
    question_id: str = typer.Option(
        None, "--question-id", help="select a stored research question by id"
    ),
    out: Path = typer.Option(
        None, "--out", help="write the evidence table as CSV to this path (e.g. "
        "results/processed/evidence_table.csv)"
    ),
    min_confidence: float = typer.Option(
        0.0, "--min-confidence", help="only include claims with confidence >= this value"
    ),
    limit: int = typer.Option(
        None, "--limit", "-n", help="keep only the top N rows after sorting"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the evidence table as JSON instead of text"
    ),
) -> None:
    """Build an evidence table for a research question (transparent, non-LLM baseline).

    Each row is one extracted claim that mentions a question entity, carrying full
    provenance (paper, exact snippet span, claim method), recognized entity names,
    database links (UniProt/HGNC xrefs + Open Targets-style associations), and a
    *heuristic textual* support/conflict/unknown label. The label describes how the
    sentence's phrasing reads (asserts vs. negates a relationship) — it is NOT a
    biological or clinical verdict (see docs/SAFETY.md). Levels are kept separate:
    the snippet is an extracted claim, entity names are observed metadata, database
    links are inferred relations.
    """
    from bioscientist_os.evidence import load_evidence

    if question is None and question_id is None:
        typer.echo("provide --question \"<text>\" or --question-id <id>", err=True)
        raise typer.Exit(code=2)

    try:
        report = load_evidence(
            db,
            question_text=question,
            question_id=question_id,
            min_confidence=min_confidence,
            limit=limit,
        )
    except ValueError:
        typer.echo(
            f"{db} is not a bioscientist-os database (no ingested tables). "
            "Run: biosci ingest data/fixtures --db " + str(db),
            err=True,
        )
        raise typer.Exit(code=1) from None
    except KeyError:
        typer.echo(f"no stored research question with id {question_id!r} in {db}", err=True)
        raise typer.Exit(code=1) from None

    if out is not None:
        _write_evidence_csv(out, report)

    if json_output:
        typer.echo(_json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    counts = report.support_counts()
    q = report.question
    lines = [
        f'Evidence table: "{q.text}"',
        f"  question_id={q.question_id}  data_source={report.data_source}",
        f"  question entities: {', '.join(report.question_entity_names) or '(none recognized)'}",
    ]
    if report.unmatched_terms:
        lines.append(
            "  unmatched entities_of_interest (not in dictionary): "
            + ", ".join(report.unmatched_terms)
        )
    lines += [
        f"  rows={report.num_rows} of {report.total_claims} corpus claims "
        f"(support={counts['support']}, conflict={counts['conflict']}, "
        f"unknown={counts['unknown']})"
        + (f"  [min_confidence={min_confidence}]" if min_confidence > 0 else "")
        + (f"  [limit={limit}]" if limit is not None else ""),
        f"  provenance coverage: {report.provenance_coverage:.0%} of rows "
        "name a paper and a source snippet",
        "",
    ]
    if not report.rows:
        lines.append("  (no claim mentions a recognized question entity)")
    for r in report.rows:
        links = ", ".join(r.database_links) or "—"
        lines.append(
            f"  [{r.support_conflict_unknown.value:>8}] conf={r.confidence:.2f}  "
            f"{r.claim_id}  ({r.paper_id})"
        )
        lines.append(f"        {r.claim_text!r}")
        lines.append(f"        entities: {', '.join(r.entity_names) or '—'}")
        lines.append(f"        db links: {links}")
        lines.append(f"        notes: {r.notes}")
    lines += [
        "",
        "support/conflict/unknown is a heuristic textual signal, not a biological or "
        "clinical verdict; database links are inferred relations (see docs/SAFETY.md).",
    ]
    if out is not None:
        lines.append(f"Wrote {out}  ({report.num_rows} rows)")
    typer.echo("\n".join(lines))


def _write_evidence_csv(path: Path, report) -> None:
    """Write an :class:`EvidenceReport` to ``path`` as CSV (creates parent dirs)."""
    import csv

    from bioscientist_os.evidence import EvidenceReport

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(EvidenceReport.EVIDENCE_COLUMNS))
        writer.writeheader()
        writer.writerows(report.evidence_rows())


def main() -> None:
    """Console-script entry point (``biosci`` / ``python -m bioscientist_os``)."""
    app()


if __name__ == "__main__":
    main()
