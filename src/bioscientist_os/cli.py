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

Later milestones add the remaining data subcommands defined in ``docs/PLAN.md``
(``evidence``, ``eval``, ``memo``). The console entry point is
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
        "Status: fixture ingestion, local SQLite storage, and CPU-only search + "
        "topic grouping available (Milestones 0-3).",
        "Extraction, evidence, and memo subcommands land milestone by milestone —",
        "see docs/PLAN.md and the website Milestones page.",
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


def main() -> None:
    """Console-script entry point (``biosci`` / ``python -m bioscientist_os``)."""
    app()


if __name__ == "__main__":
    main()
