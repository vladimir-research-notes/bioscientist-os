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

Milestone 6 adds the offline-first database-connector subcommands:

* ``biosci db sources --db <path>``                  — list the available connectors;
* ``biosci db list --source <name> --db <path>``     — list a source's record ids;
* ``biosci db lookup --source <name> --id <id> --db <path> [--cache]`` — fetch one
  record, showing its ``data_source`` provenance (fixture / cache / live).

Milestone 7 adds figure generation over the workbench's own reports:

* ``biosci figures --db <path> [--out-dir <dir>] [--no-render] [--json]`` — build the
  five figures' inspectable data (literature timeline, topic-cluster summary,
  claim/evidence matrix, entity/database-link graph, support-vs-conflict table),
  always write ``visualizations.json``, and render PNGs when the optional
  ``matplotlib`` extra is installed.

Milestone 8 adds the self-evaluation harness over the workbench's own outputs:

* ``biosci eval --db <path> [--out <json>]`` — score ingestion correctness, BM25F
  search recall on labeled queries, dictionary entity precision/recall against gold
  sets, claim-extraction sanity, evidence-table completeness, and provenance
  coverage, each reported with its denominator and a 95% Wilson interval.

Later milestones add the remaining data subcommand defined in ``docs/PLAN.md``
(``memo``). The console entry point is
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
        "grouping, rule-based entity/claim extraction, evidence-table assembly, an "
        "offline-first database-connector layer, workbench figures, and a gold-label "
        "self-evaluation harness available (Milestones 0-8).",
        "The memo subcommand lands milestone by milestone — see "
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


@app.command()
def figures(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to visualize"
    ),
    out_dir: Path = typer.Option(
        Path("results") / "figures",
        "--out-dir",
        help="directory for visualizations.json and the PNGs (default: results/figures)",
    ),
    question: str = typer.Option(
        None, "--question", "-q",
        help="research question (text or stored id) for the evidence matrix",
    ),
    question_id: str = typer.Option(
        None, "--question-id", help="select the evidence-matrix question by stored id"
    ),
    threshold: float = typer.Option(
        None, "--threshold",
        help="topic-cluster cosine threshold (default: the documented baseline)",
    ),
    no_render: bool = typer.Option(
        False, "--no-render", help="write the figure data only; never render PNGs"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the figure data as JSON instead of text"
    ),
) -> None:
    """Generate the workbench figures (data always; PNGs when matplotlib is installed).

    Builds five figures from the workbench's own transparent reports — a literature
    timeline (observed metadata), the M3 topic-cluster summary, a claim/evidence
    matrix (papers x question entities), an entity/database-link graph, and a
    support-vs-conflict table. The inspectable figure *data* is always written to
    ``visualizations.json``; PNGs are rendered only with the optional ``matplotlib``
    extra (``pip install -e '.[viz]'``). The matrix's support/conflict/unknown cells
    and the link graph's database edges are heuristic / inferred respectively, NOT
    biological or clinical verdicts (see docs/SAFETY.md).
    """
    from bioscientist_os.search import DEFAULT_THRESHOLD
    from bioscientist_os.visualization import load_visualizations, write_visualizations

    try:
        report = load_visualizations(
            db,
            question_text=question,
            question_id=question_id,
            threshold=DEFAULT_THRESHOLD if threshold is None else threshold,
        )
    except ValueError as exc:
        # Either "not a bioscientist-os database" or "no research question available".
        if "not a bioscientist-os database" in str(exc):
            typer.echo(
                f"{db} is not a bioscientist-os database (no ingested tables). "
                "Run: biosci ingest data/fixtures --db " + str(db),
                err=True,
            )
        else:
            typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    except KeyError:
        typer.echo(f"no stored research question with id {question_id!r} in {db}", err=True)
        raise typer.Exit(code=1) from None

    if json_output:
        typer.echo(_json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    artifacts = write_visualizations(report, out_dir, render=not no_render)

    tl = report.timeline
    cl = report.clusters
    mx = report.matrix
    lg = report.link_graph
    totals = report.support_table.totals()
    lines = [
        f"Figures from {db}  (data_source={report.data_source})",
        f"  timeline        : {tl.total_papers} papers across {tl.num_years} years"
        + (f" ({tl.undated} undated)" if tl.undated else ""),
        f"  topic clusters  : {cl.num_groups} groups ({cl.num_singletons} singleton) "
        f"at threshold {cl.threshold}",
        f"  evidence matrix : {mx.question_id} — {mx.shape[0]} papers x "
        f"{mx.shape[1]} entities ({mx.num_rows_used} claim rows)",
        f"  link graph      : {len(lg.nodes)} nodes, {len(lg.edges)} edges "
        f"(nodes {lg.node_counts()}; edges {lg.edge_counts()})",
        f"  support table   : {len(report.support_table.rows)} questions — "
        f"support={totals['support']} conflict={totals['conflict']} unknown={totals['unknown']}",
        "",
        f"Wrote {artifacts.json_path}",
    ]
    if artifacts.rendered:
        for key in report.FIGURE_KEYS:
            lines.append(f"Wrote {artifacts.figure_paths[key]}")
    elif no_render:
        lines.append("(--no-render: PNGs skipped; figure data written to JSON only)")
    else:
        lines.append(
            "(matplotlib not installed: PNGs skipped; install with  pip install -e '.[viz]'  "
            "— figure data was written to JSON)"
        )
    lines += [
        "",
        "Matrix support/conflict/unknown is a heuristic textual signal and link-graph "
        "database edges are inferred relations — neither is a biological or clinical "
        "verdict (see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


@app.command("eval")
def eval_cmd(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database to evaluate"
    ),
    out: Path = typer.Option(
        None, "--out", help="write the eval report as JSON to this path (e.g. "
        "results/processed/eval_report.json)"
    ),
    confidence: float = typer.Option(
        0.95, "--confidence", help="confidence level for the Wilson intervals (default: 0.95)"
    ),
    recall_k: list[int] = typer.Option(
        None, "--recall-k", help="recall@k cut-off; repeatable (default: 3 and 5)"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="emit the report as JSON instead of text"
    ),
) -> None:
    """Evaluate the workbench against committed gold labels (offline, deterministic).

    Scores the *pipeline* — not biological truth — on the fixed fixture corpus:
    ingestion correctness, BM25F search recall@k on labeled queries, dictionary
    entity precision/recall against gold sets, claim-extraction sanity,
    evidence-table completeness, and provenance coverage. Every rate is reported
    with its denominator and a Wilson confidence interval; small N is stated
    honestly and heterogeneous tasks are never collapsed into one number
    (see docs/EVALUATION.md and docs/SAFETY.md).
    """
    from bioscientist_os.evals import DEFAULT_RECALL_K, run_eval

    if not 0.0 < confidence < 1.0:
        typer.echo("--confidence must be in (0, 1)", err=True)
        raise typer.Exit(code=2)
    ks = tuple(recall_k) if recall_k else DEFAULT_RECALL_K

    try:
        report = run_eval(db, confidence=confidence, recall_k=ks)
    except ValueError as exc:
        if "not a bioscientist-os database" in str(exc):
            typer.echo(
                f"{db} is not a bioscientist-os database (no ingested tables). "
                "Run: biosci ingest data/fixtures --db " + str(db),
                err=True,
            )
        else:
            typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            _json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )

    if json_output:
        typer.echo(_json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return

    typer.echo(report.format_text())
    if out is not None:
        typer.echo(f"\nWrote {out}")


# ---------------------------------------------------------------------------
# Milestone 6 — database connectors (`biosci db ...`)
# ---------------------------------------------------------------------------

# The default cache directory for `db lookup --cache`. Gitignored (see .gitignore);
# resolved relative to the current working directory (normally the repo root).
DEFAULT_CACHE_DIR = Path("data") / "cache"

# Shared help text for the `--source` option of the db subcommands.
_SOURCE_HELP = "connector name: uniprot / opentargets / papers"

db_app = typer.Typer(
    name="db",
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Offline-first database connectors: look up UniProt-style proteins, Open "
        "Targets-style associations, and paper metadata by id, with explicit "
        "data_source provenance (fixture / cache / live). Live sources are opt-in "
        "and never used here (see docs/DATABASES.md)."
    ),
)
app.add_typer(db_app, name="db")


def _open_registry_or_exit(db: Path):
    """Open ``db`` and build the connector registry, or print the error and exit 1."""
    from bioscientist_os.databases import open_connectors

    try:
        return open_connectors(db)
    except ValueError:
        typer.echo(
            f"{db} is not a bioscientist-os database (no ingested tables). "
            "Run: biosci ingest data/fixtures --db " + str(db),
            err=True,
        )
        raise typer.Exit(code=1) from None


def _connector_or_exit(registry, source: str):
    """Return the named connector, or list the valid names and exit 2."""
    if source not in registry:
        typer.echo(
            f"unknown source {source!r}; available: {', '.join(registry.names())}",
            err=True,
        )
        raise typer.Exit(code=2)
    return registry.get(source)


def _record_payload(record) -> dict:
    """A JSON-friendly view of a fetched record, with provenance surfaced on top."""
    dumped = record.model_dump(mode="json")
    return {
        "record_id": dumped.get("record_id") or dumped.get("paper_id"),
        "source": getattr(record, "source", None),
        "data_source": record.data_source.value,
        "synthetic": getattr(record, "synthetic", None),
        "record": dumped,
    }


@db_app.command("sources")
def db_sources(
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database"
    ),
    json_output: bool = typer.Option(False, "--json", help="emit JSON instead of text"),
) -> None:
    """List the available connectors and how many records each holds."""
    registry = _open_registry_or_exit(db)
    rows = registry.describe()
    if json_output:
        typer.echo(_json.dumps({"db": str(db), "connectors": rows}, indent=2, sort_keys=True))
        return
    lines = [f"Connectors for {db}:"]
    for r in rows:
        lines.append(
            f"  {r['name']:<12} source={r['source']:<12} type={r['record_type']:<11} "
            f"records={r['count']}  data_source={r['data_source']}"
        )
    lines += [
        "",
        "All connectors are fixture-backed (data_source=fixture); cache (--cache) and "
        "live sources are opt-in (see docs/DATABASES.md).",
    ]
    typer.echo("\n".join(lines))


@db_app.command("list")
def db_list(
    source: str = typer.Option(..., "--source", help=_SOURCE_HELP),
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database"
    ),
    json_output: bool = typer.Option(False, "--json", help="emit JSON instead of text"),
) -> None:
    """List the record ids a source can serve."""
    registry = _open_registry_or_exit(db)
    connector = _connector_or_exit(registry, source)
    ids = connector.ids()
    if json_output:
        typer.echo(
            _json.dumps(
                {"source": source, "data_source": connector.data_source.value, "ids": ids},
                indent=2,
                sort_keys=True,
            )
        )
        return
    lines = [f"{source}: {len(ids)} record id(s)  (data_source={connector.data_source.value})"]
    lines += [f"  {rid}" for rid in ids]
    typer.echo("\n".join(lines))


@db_app.command("lookup")
def db_lookup(
    source: str = typer.Option(..., "--source", help=_SOURCE_HELP),
    record_id: str = typer.Option(..., "--id", help="record id, e.g. P05231 or biosci-paper-001"),
    db: Path = typer.Option(
        ..., "--db", exists=True, dir_okay=False, help="ingested SQLite database"
    ),
    cache: bool = typer.Option(
        False, "--cache", help="serve through a local read-through cache (data/cache/, gitignored)"
    ),
    cache_dir: Path = typer.Option(
        DEFAULT_CACHE_DIR, "--cache-dir", help="cache directory for --cache (default: data/cache)"
    ),
    json_output: bool = typer.Option(False, "--json", help="emit JSON instead of text"),
) -> None:
    """Fetch one record by id, showing its data_source provenance.

    A fixture lookup reports ``data_source=fixture``. With ``--cache``, the first
    lookup reports the underlying source and writes a cache copy; a second lookup of
    the same id reports ``data_source=cache`` (served from the local file, offline).
    The record is observed metadata — no claim, relation, or biological assertion is
    made (see docs/SAFETY.md).
    """
    from bioscientist_os.databases import CachedConnector, RecordNotFound

    registry = _open_registry_or_exit(db)
    connector = _connector_or_exit(registry, source)
    if cache:
        connector = CachedConnector(connector, cache_dir)

    try:
        record = connector.get(record_id)
    except RecordNotFound:
        typer.echo(f"no record {record_id!r} in source {source!r} ({db})", err=True)
        raise typer.Exit(code=1) from None

    payload = _record_payload(record)
    if json_output:
        typer.echo(_json.dumps(payload, indent=2, sort_keys=True))
        return
    lines = [
        f"{source}/{payload['record_id']}  (data_source={payload['data_source']}, "
        f"synthetic={payload['synthetic']})",
    ]
    for key, value in sorted(payload["record"].items()):
        if key in ("data_source",):
            continue
        lines.append(f"  {key}: {value}")
    lines += [
        "",
        "Observed metadata served by a connector; data_source is its provenance "
        "(fixture / cache / live). Not a clinical or diagnostic data source "
        "(see docs/SAFETY.md).",
    ]
    typer.echo("\n".join(lines))


def main() -> None:
    """Console-script entry point (``biosci`` / ``python -m bioscientist_os``)."""
    app()


if __name__ == "__main__":
    main()
