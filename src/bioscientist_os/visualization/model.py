"""Inspectable *data* behind every workbench figure (Milestone 7).

The discipline of this milestone is to keep the **figure data** — the numbers a
figure draws — separate from the **rendering** (the PNG). These frozen
dataclasses are the figure data: they are pure, ``matplotlib``-free, deterministic,
JSON-serializable, and carry the same provenance the rest of the package does
(``data_source``, a named ``method``, and explicit denominators). The rendering
layer (:mod:`bioscientist_os.visualization.figures`) is an *optional* skin over
them; ``scripts/05_generate_visualizations.py`` always writes the data as
``results/figures/visualizations.json`` even when ``matplotlib`` is absent, so the
chain stays inspectable on the light core path.

Five figures, matching ``docs/PLAN.md``:

* :class:`TimelineSeries` — papers per publication year (observed metadata);
* :class:`ClusterSummary` — the M3 topic groups and their sizes/labels;
* :class:`EvidenceMatrix` — papers × question-entities, each cell the strongest
  support/conflict/unknown *textual* signal linking them (NOT a biological verdict);
* :class:`LinkGraph` — entities, their database links (UniProt/HGNC/Open Targets),
  and claim co-occurrence edges (an inferred-relation view);
* :class:`SupportConflictTable` — per-research-question support/conflict/unknown
  counts.

Two epistemic reminders are baked into the captions rather than left to a reader:
the support/conflict signal is heuristic and textual (see :func:`classify_support`
and ``docs/SAFETY.md``), and the database links are *inferred relations* assembled
by combining records — neither is a claim about biological truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


class VisualizationError(RuntimeError):
    """Raised when a figure cannot be produced (e.g. ``matplotlib`` is absent)."""


# Stable order + filenames for the five figures, used by the report, the renderer,
# the CLI, and the script so they never disagree on what exists or what it's called.
FIGURE_FILENAMES: dict[str, str] = {
    "timeline": "timeline.png",
    "topic_clusters": "topic_clusters.png",
    "evidence_matrix": "evidence_matrix.png",
    "link_graph": "link_graph.png",
    "support_conflict": "support_conflict.png",
}


@dataclass(frozen=True)
class TimelineSeries:
    """Literature timeline: how many papers were published per year.

    ``points`` is ``[(year, count), ...]`` sorted ascending by year; ``undated`` is
    the number of papers with no ``year`` (surfaced, not dropped). Counts are over
    *observed metadata* — they say nothing about the papers' content or quality.
    """

    points: list[tuple[int, int]]
    undated: int
    total_papers: int
    data_source: str
    method: str = "count of papers by publication year"
    caption: str = (
        "Papers per publication year (observed metadata). Counts describe the "
        "fixture corpus, not a field-wide publication trend."
    )

    @property
    def num_years(self) -> int:
        return len(self.points)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "caption": self.caption,
            "data_source": self.data_source,
            "total_papers": self.total_papers,
            "undated": self.undated,
            "num_years": self.num_years,
            "points": [[year, count] for year, count in self.points],
        }


@dataclass(frozen=True)
class ClusterBar:
    """One topic group's size and label terms, for the cluster-summary figure."""

    topic_id: str
    size: int
    label_terms: list[str]

    def to_dict(self) -> dict:
        return {"topic_id": self.topic_id, "size": self.size, "label_terms": self.label_terms}


@dataclass(frozen=True)
class ClusterSummary:
    """Topic-cluster summary: the M3 single-link cosine groups and their sizes.

    A view of :class:`~bioscientist_os.search.model.TopicReport`: ``bars`` are the
    groups (largest first, as the topic report orders them). The labels describe a
    group; they are not asserted topics of the field.
    """

    bars: list[ClusterBar]
    threshold: float
    num_groups: int
    num_singletons: int
    total_papers: int
    data_source: str
    method: str = "single-link cosine clustering (connected components)"
    caption: str = (
        "Topic groups by single-link cosine clustering. Group labels are distinctive "
        "terms describing a group, not asserted topics of the field."
    )

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "caption": self.caption,
            "data_source": self.data_source,
            "threshold": self.threshold,
            "total_papers": self.total_papers,
            "num_groups": self.num_groups,
            "num_singletons": self.num_singletons,
            "bars": [b.to_dict() for b in self.bars],
        }


# The cell vocabulary of the evidence matrix. ``none`` means no claim in that paper
# links to that question entity (an honest gap), distinct from ``unknown`` (a claim
# exists but its phrasing neither affirms nor negates a relationship).
MATRIX_CELL_VALUES: tuple[str, ...] = ("support", "conflict", "unknown", "none")


@dataclass(frozen=True)
class EvidenceMatrix:
    """Claim/evidence matrix for one research question: papers × question entities.

    ``cells[r][c]`` is one of :data:`MATRIX_CELL_VALUES` — the support/conflict/
    unknown label of the **highest-confidence** evidence row linking paper
    ``paper_ids[r]`` to question entity ``entity_names[c]`` (ties broken by smallest
    ``claim_id``), or ``"none"`` if no such row exists.

    The cell is a heuristic *textual* signal about a single sentence's phrasing — it
    is **not** a biological or clinical verdict, and the matrix does not detect
    cross-paper directional conflict (see :class:`SupportLabel` and ``docs/SAFETY.md``).
    """

    question_id: str
    question_text: str
    paper_ids: list[str]
    entity_names: list[str]
    cells: list[list[str]]
    num_rows_used: int
    data_source: str
    method: str = "highest-confidence support label per (paper, question entity)"
    caption: str = (
        "Per-cell support/conflict/unknown is a heuristic textual signal about one "
        "sentence's phrasing, NOT a biological or clinical verdict; it does not "
        "detect cross-paper directional conflict."
    )

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.paper_ids), len(self.entity_names))

    def cell_counts(self) -> dict[str, int]:
        """Count of cells per value (all of :data:`MATRIX_CELL_VALUES` present)."""
        counts = {v: 0 for v in MATRIX_CELL_VALUES}
        for row in self.cells:
            for value in row:
                counts[value] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "caption": self.caption,
            "data_source": self.data_source,
            "question_id": self.question_id,
            "question_text": self.question_text,
            "shape": list(self.shape),
            "num_rows_used": self.num_rows_used,
            "paper_ids": list(self.paper_ids),
            "entity_names": list(self.entity_names),
            "cells": [list(row) for row in self.cells],
            "cell_counts": self.cell_counts(),
        }


@dataclass(frozen=True)
class GraphNode:
    """A node in the entity/database-link graph: an entity or a database record."""

    node_id: str
    label: str
    kind: str  # "entity" | "database"
    entity_type: str | None = None  # for entity nodes (gene/protein/process/...)
    degree: int = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "entity_type": self.entity_type,
            "degree": self.degree,
        }


@dataclass(frozen=True)
class GraphEdge:
    """An undirected edge: entity↔database link, or entity↔entity co-occurrence."""

    source: str
    target: str
    kind: str  # "xref" | "association" | "co-occurrence"

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass(frozen=True)
class LinkGraph:
    """Entity / database-link graph (an inferred-relation view of the corpus).

    Nodes are recognized entities (those appearing in ≥1 extracted claim) and the
    database records they reference; edges are entity→database cross-references
    (``xref``: UniProt/HGNC), entity→association (``association``: Open Targets), and
    entity↔entity claim ``co-occurrence``. The cross-reference and association edges
    are *inferred relations* (assembled by combining records), never claims of
    biological truth.
    """

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    data_source: str
    method: str = "entity db-xrefs + Open Targets associations + claim co-occurrence"
    caption: str = (
        "Entities and their database links (inferred relations from combining records) "
        "plus claim co-occurrence edges. Edges are not claims of biological truth."
    )

    def node_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for n in self.nodes:
            counts[n.kind] = counts.get(n.kind, 0) + 1
        return dict(sorted(counts.items()))

    def edge_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.edges:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "caption": self.caption,
            "data_source": self.data_source,
            "num_nodes": len(self.nodes),
            "num_edges": len(self.edges),
            "node_counts": self.node_counts(),
            "edge_counts": self.edge_counts(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }


@dataclass(frozen=True)
class SupportConflictRow:
    """One research question's support/conflict/unknown counts."""

    question_id: str
    question_text: str
    support: int
    conflict: int
    unknown: int

    @property
    def total(self) -> int:
        return self.support + self.conflict + self.unknown

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "support": self.support,
            "conflict": self.conflict,
            "unknown": self.unknown,
            "total": self.total,
        }


@dataclass(frozen=True)
class SupportConflictTable:
    """Support-vs-conflict table: per-question support/conflict/unknown row counts.

    Aggregates the M5 evidence tables. The counts describe how each row's *sentence*
    reads (the :func:`classify_support` heuristic), not whether papers agree on a
    biological fact — see the caption and ``docs/SAFETY.md``.
    """

    rows: list[SupportConflictRow]
    data_source: str
    method: str = "rule:support-cues counts per research question"
    caption: str = (
        "Support/conflict/unknown counts per research question. A heuristic textual "
        "signal, never a biological or clinical verdict."
    )

    def totals(self) -> dict[str, int]:
        return {
            "support": sum(r.support for r in self.rows),
            "conflict": sum(r.conflict for r in self.rows),
            "unknown": sum(r.unknown for r in self.rows),
            "total": sum(r.total for r in self.rows),
        }

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "caption": self.caption,
            "data_source": self.data_source,
            "rows": [r.to_dict() for r in self.rows],
            "totals": self.totals(),
        }


@dataclass(frozen=True)
class VisualizationReport:
    """All five figures' data for one corpus, plus the parameters that produced it.

    The single object the renderer and the CLI/script consume. :meth:`figures`
    returns the five data objects keyed by the stable figure keys in
    :data:`FIGURE_FILENAMES`, so callers iterate uniformly.
    """

    timeline: TimelineSeries
    clusters: ClusterSummary
    matrix: EvidenceMatrix
    link_graph: LinkGraph
    support_table: SupportConflictTable
    data_source: str
    params: dict[str, object] = field(default_factory=dict)

    FIGURE_KEYS: ClassVar[tuple[str, ...]] = tuple(FIGURE_FILENAMES)

    def figures(self) -> dict[str, object]:
        return {
            "timeline": self.timeline,
            "topic_clusters": self.clusters,
            "evidence_matrix": self.matrix,
            "link_graph": self.link_graph,
            "support_conflict": self.support_table,
        }

    def to_dict(self) -> dict:
        return {
            "data_source": self.data_source,
            "params": self.params,
            "figures": {key: fig.to_dict() for key, fig in self.figures().items()},
        }


__all__ = [
    "VisualizationError",
    "FIGURE_FILENAMES",
    "MATRIX_CELL_VALUES",
    "TimelineSeries",
    "ClusterBar",
    "ClusterSummary",
    "EvidenceMatrix",
    "GraphNode",
    "GraphEdge",
    "LinkGraph",
    "SupportConflictRow",
    "SupportConflictTable",
    "VisualizationReport",
]
