"""Build the figure data from the workbench's own reports (Milestone 7).

Pure, ``matplotlib``-free functions that turn the existing pipeline outputs into the
:mod:`bioscientist_os.visualization.model` dataclasses. They reuse the same
transparent baselines the rest of the package exposes — the M3 topic grouping, the
M4 dictionary/extraction, and the M5 evidence-table builder — so a figure never
introduces a new, unaudited computation; it only *re-presents* what those layers
already produced, with provenance intact.

Everything is deterministic: papers, entities, nodes, and edges are all sorted
before they enter a figure, so the JSON written by the script is byte-identical
across runs (PNG bytes may still vary by ``matplotlib`` version — only the *data* is
guaranteed stable).

The database-backed :func:`load_visualizations` mirrors
:func:`bioscientist_os.evidence.load_evidence` / :func:`bioscientist_os.search.load_index`:
it opens an ingested SQLite database, rebuilds the dictionary and extraction once,
and assembles all five figures (one evidence table per stored question for the
support-vs-conflict table, plus a chosen *primary* question for the matrix).
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations
from pathlib import Path

from bioscientist_os.evidence.dictionary import EntityDictionary, build_dictionary
from bioscientist_os.evidence.extract import extract_corpus
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.evidence.table import (
    EvidenceReport,
    build_evidence_report,
    resolve_question,
)
from bioscientist_os.schemas import DatabaseRecord, Paper, ResearchQuestion
from bioscientist_os.search import DEFAULT_THRESHOLD, SearchIndex, group_topics
from bioscientist_os.visualization.model import (
    ClusterBar,
    ClusterSummary,
    EvidenceMatrix,
    GraphEdge,
    GraphNode,
    LinkGraph,
    SupportConflictRow,
    SupportConflictTable,
    TimelineSeries,
    VisualizationReport,
)

# Open Targets-style association source name (matches the fixtures / connectors).
_ASSOCIATION_SOURCE = "OpenTargets"


def _corpus_data_source(papers: Iterable[Paper]) -> str:
    """The single ``data_source`` of a corpus, or ``"mixed"`` (mirrors SearchIndex)."""
    sources = {p.data_source.value for p in papers}
    if not sources:
        return "fixture"
    return next(iter(sources)) if len(sources) == 1 else "mixed"


# -- 1. literature timeline ------------------------------------------------


def build_timeline(papers: Iterable[Paper]) -> TimelineSeries:
    """Count papers by publication year; surface (not drop) undated papers."""
    papers = list(papers)
    by_year: dict[int, int] = {}
    undated = 0
    for p in papers:
        if p.year is None:
            undated += 1
        else:
            by_year[p.year] = by_year.get(p.year, 0) + 1
    points = sorted(by_year.items())
    return TimelineSeries(
        points=points,
        undated=undated,
        total_papers=len(papers),
        data_source=_corpus_data_source(papers),
    )


# -- 2. topic-cluster summary ----------------------------------------------


def build_cluster_summary(
    index: SearchIndex, *, threshold: float = DEFAULT_THRESHOLD
) -> ClusterSummary:
    """Summarize the M3 single-link cosine topic groups (sizes + label terms)."""
    report = group_topics(index, threshold=threshold)
    bars = [
        ClusterBar(topic_id=g.topic_id, size=g.size, label_terms=list(g.label_terms))
        for g in report.groups
    ]
    return ClusterSummary(
        bars=bars,
        threshold=report.threshold,
        num_groups=report.num_groups,
        num_singletons=report.num_singletons,
        total_papers=report.total_papers,
        data_source=report.data_source,
        method=report.method,
    )


# -- 3. claim / evidence matrix --------------------------------------------


def build_evidence_matrix(report: EvidenceReport) -> EvidenceMatrix:
    """Papers × question entities; each cell the strongest support label linking them.

    For every (paper, question entity) pair, pick the evidence row with the highest
    confidence (ties → smallest ``claim_id``) and use its support label; pairs with
    no row are ``"none"``. Columns are *all* question entities (so coverage gaps show
    honestly), rows are the papers that contributed at least one row, sorted.
    """
    entity_names = list(report.question_entity_names)
    # best[(paper_id, entity_name)] = (confidence, claim_id, label)
    best: dict[tuple[str, str], tuple[float, str, str]] = {}
    paper_ids: set[str] = set()
    for r in report.rows:
        paper_ids.add(r.paper_id)
        label = r.support_conflict_unknown.value
        row_entities = set(r.entity_names)
        for ename in entity_names:
            if ename not in row_entities:
                continue
            key = (r.paper_id, ename)
            cand = (r.confidence, r.claim_id, label)
            cur = best.get(key)
            # Higher confidence wins; on a tie the smaller claim_id wins (stable).
            if cur is None or cand[0] > cur[0] or (cand[0] == cur[0] and cand[1] < cur[1]):
                best[key] = cand

    ordered_papers = sorted(paper_ids)
    cells = [
        [best.get((pid, ename), (0.0, "", "none"))[2] for ename in entity_names]
        for pid in ordered_papers
    ]
    return EvidenceMatrix(
        question_id=report.question.question_id,
        question_text=report.question.text,
        paper_ids=ordered_papers,
        entity_names=entity_names,
        cells=cells,
        num_rows_used=report.num_rows,
        data_source=report.data_source,
    )


# -- 4. entity / database-link graph ---------------------------------------


def _gene_to_entity(dictionary: EntityDictionary) -> dict[str, str]:
    """Map an HGNC gene symbol to its entity id (first one wins), like the M5 builder."""
    gene_to_eid: dict[str, str] = {}
    for eid, ent in dictionary.entities.items():
        gene = ent.db_xrefs.get("HGNC")
        if gene:
            gene_to_eid.setdefault(gene, eid)
    return gene_to_eid


def build_link_graph(
    extraction: ExtractionReport,
    dictionary: EntityDictionary,
    records: Iterable[DatabaseRecord],
) -> LinkGraph:
    """Build the entity/database-link graph from the extraction, dictionary, and records.

    Includes only entities that appear in ≥1 extracted claim (the ones that carry
    evidence). For each, add its ``db_xrefs`` as ``xref`` edges and any Open
    Targets-style association naming its gene as an ``association`` edge; add an
    undirected ``co-occurrence`` edge between two entities sharing a claim. Mirrors
    the M5 evidence-table's link assembly so the two never disagree.
    """
    records = list(records)
    gene_to_eid = _gene_to_entity(dictionary)
    assoc_by_eid: dict[str, list[DatabaseRecord]] = {}
    for r in records:
        if r.record_type != "association":
            continue
        gene = r.fields.get("target_gene")
        eid = gene_to_eid.get(gene) if isinstance(gene, str) else None
        if eid is not None:
            assoc_by_eid.setdefault(eid, []).append(r)

    # Entities that actually appear in claims, and claim-level co-occurrence pairs.
    active: set[str] = set()
    cooccur: set[tuple[str, str]] = set()
    for claim in extraction.all_claims:
        eids = sorted(set(claim.entity_ids))
        active.update(eids)
        for a, b in combinations(eids, 2):
            cooccur.add((a, b))  # a < b by construction (sorted)

    entity_names = extraction.entity_name_by_id()
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    degree: dict[str, int] = {}

    def _bump(node_id: str) -> None:
        degree[node_id] = degree.get(node_id, 0) + 1

    def _ensure_entity(eid: str) -> None:
        if eid in nodes:
            return
        ent = dictionary.entities.get(eid)
        label = ent.canonical_name if ent is not None else entity_names.get(eid, eid)
        etype = ent.entity_type.value if ent is not None else None
        nodes[eid] = GraphNode(node_id=eid, label=label, kind="entity", entity_type=etype)

    def _ensure_db(node_id: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = GraphNode(node_id=node_id, label=node_id, kind="database")

    for eid in sorted(active):
        _ensure_entity(eid)
        ent = dictionary.entities.get(eid)
        if ent is not None:
            for db, acc in sorted(ent.db_xrefs.items()):
                db_id = f"{db}:{acc}"
                _ensure_db(db_id)
                edges.append(GraphEdge(source=eid, target=db_id, kind="xref"))
                _bump(eid)
                _bump(db_id)
        for rec in assoc_by_eid.get(eid, []):
            db_id = f"{rec.source}:{rec.record_id}"
            _ensure_db(db_id)
            edges.append(GraphEdge(source=eid, target=db_id, kind="association"))
            _bump(eid)
            _bump(db_id)

    for a, b in sorted(cooccur):
        if a in active and b in active:
            _ensure_entity(a)
            _ensure_entity(b)
            edges.append(GraphEdge(source=a, target=b, kind="co-occurrence"))
            _bump(a)
            _bump(b)

    # Freeze nodes with their final degree, sorted by (kind, node_id) for determinism;
    # sort edges by (source, target, kind).
    final_nodes = [
        GraphNode(
            node_id=n.node_id,
            label=n.label,
            kind=n.kind,
            entity_type=n.entity_type,
            degree=degree.get(n.node_id, 0),
        )
        for n in sorted(nodes.values(), key=lambda n: (n.kind, n.node_id))
    ]
    edges.sort(key=lambda e: (e.source, e.target, e.kind))
    return LinkGraph(
        nodes=final_nodes,
        edges=edges,
        data_source=extraction.data_source if extraction.data_source != "mixed" else "fixture",
    )


# -- 5. support-vs-conflict table ------------------------------------------


def build_support_conflict_table(reports: Iterable[EvidenceReport]) -> SupportConflictTable:
    """Aggregate per-question support/conflict/unknown counts from evidence tables."""
    rows: list[SupportConflictRow] = []
    sources: set[str] = set()
    for report in reports:
        counts = report.support_counts()
        sources.add(report.data_source)
        rows.append(
            SupportConflictRow(
                question_id=report.question.question_id,
                question_text=report.question.text,
                support=counts["support"],
                conflict=counts["conflict"],
                unknown=counts["unknown"],
            )
        )
    data_source = next(iter(sources)) if len(sources) == 1 else "fixture"
    return SupportConflictTable(rows=rows, data_source=data_source)


# -- assembly + database-backed convenience --------------------------------


def build_visualization_report(
    papers: list[Paper],
    records: list[DatabaseRecord],
    questions: list[ResearchQuestion],
    *,
    question_text: str | None = None,
    question_id: str | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> VisualizationReport:
    """Assemble all five figures from an in-memory corpus.

    One evidence table is built per stored question for the support-vs-conflict
    table; the *primary* question (resolved from ``question_text`` / ``question_id``,
    defaulting to the first stored question) drives the evidence matrix.
    """
    dictionary = build_dictionary(records)
    extraction = extract_corpus(papers, dictionary)
    index = SearchIndex.from_papers(papers)

    # One evidence report per stored question (for the support table), preserving
    # stored order. If there are no stored questions, fall back to the resolved one.
    per_question: list[EvidenceReport] = [
        build_evidence_report(q, extraction, dictionary, records) for q in questions
    ]

    # Resolve the primary question: an explicit selector wins; otherwise default to
    # the first stored question. With neither a selector nor any stored question
    # there is nothing to build a matrix from, which is an error.
    if question_text is not None or question_id is not None:
        primary_q = resolve_question(
            questions, dictionary, question_text=question_text, question_id=question_id
        )
    elif questions:
        primary_q = questions[0]
    else:
        raise ValueError("no research question available to build the evidence matrix")

    primary_report = next(
        (r for r in per_question if r.question.question_id == primary_q.question_id),
        None,
    )
    if primary_report is None:
        primary_report = build_evidence_report(primary_q, extraction, dictionary, records)
        per_question = per_question or [primary_report]

    return VisualizationReport(
        timeline=build_timeline(papers),
        clusters=build_cluster_summary(index, threshold=threshold),
        matrix=build_evidence_matrix(primary_report),
        link_graph=build_link_graph(extraction, dictionary, records),
        support_table=build_support_conflict_table(per_question),
        data_source=_corpus_data_source(papers),
        params={
            "threshold": threshold,
            "primary_question_id": primary_report.question.question_id,
            "num_questions": len(per_question),
        },
    )


def load_visualizations(
    db_path: str | Path,
    *,
    question_text: str | None = None,
    question_id: str | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> VisualizationReport:
    """Open an ingested SQLite database and assemble all five figures' data.

    Raises :class:`ValueError` if the file is not a bioscientist-os database (no
    ingested tables), mirroring the other database-backed subcommands.
    """
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        papers = list(store.iter_papers())
        records = list(store.iter_database_records())
        questions = list(store.iter_research_questions())

    return build_visualization_report(
        papers,
        records,
        questions,
        question_text=question_text,
        question_id=question_id,
        threshold=threshold,
    )


__all__ = [
    "build_timeline",
    "build_cluster_summary",
    "build_evidence_matrix",
    "build_link_graph",
    "build_support_conflict_table",
    "build_visualization_report",
    "load_visualizations",
]
