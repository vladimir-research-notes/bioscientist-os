"""The ``biosci`` command-line interface.

Milestone 0 ships three read-only, offline subcommands that describe the tool and
check the host:

* ``biosci version``    — print the package version;
* ``biosci info``       — print identity, the four epistemic levels, and the
                          non-clinical safety stance;
* ``biosci env-check``  — report whether this host can build and test on CPU
                          (delegates to :mod:`bioscientist_os.environment`).

Later milestones add the data subcommands defined in ``docs/PLAN.md``
(``ingest``, ``stats``, ``search``, ``topics``, ``evidence``, ``eval``,
``memo``). The console entry point is ``bioscientist_os.cli:main`` (see
``pyproject.toml``); ``python -m bioscientist_os`` routes here too via
``__main__``.
"""

from __future__ import annotations

import json as _json

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
        "Status: package skeleton (Milestone 0). Functional subcommands land",
        "milestone by milestone — see docs/PLAN.md and the website Milestones page.",
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


def main() -> None:
    """Console-script entry point (``biosci`` / ``python -m bioscientist_os``)."""
    app()


if __name__ == "__main__":
    main()
