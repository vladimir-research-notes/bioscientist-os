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

Later milestones add the remaining data subcommands defined in ``docs/PLAN.md``
(``search``, ``topics``, ``evidence``, ``eval``, ``memo``). The console entry
point is ``bioscientist_os.cli:main`` (see ``pyproject.toml``);
``python -m bioscientist_os`` routes here too via ``__main__``.
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
        "Status: fixture ingestion + local SQLite storage available "
        "(Milestones 0-2).",
        "Search, extraction, evidence, and memo subcommands land milestone by",
        "milestone — see docs/PLAN.md and the website Milestones page.",
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


def main() -> None:
    """Console-script entry point (``biosci`` / ``python -m bioscientist_os``)."""
    app()


if __name__ == "__main__":
    main()
