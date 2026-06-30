"""Workbench visualizations (Milestone 7).

Five figures that summarize the corpus and the evidence, each split into
**inspectable data** and **optional rendering**:

* a literature timeline (papers per year);
* a topic-cluster summary (the M3 single-link cosine groups);
* a claim/evidence matrix (papers × question entities, support/conflict/unknown);
* an entity / database-link graph (db-xrefs + associations + claim co-occurrence);
* a support-vs-conflict table (per research question).

The figure *data* lives in matplotlib-free, deterministic, provenance-carrying
dataclasses (:mod:`bioscientist_os.visualization.model`) built from the workbench's
own reports (:mod:`bioscientist_os.visualization.build`). Rendering to PNG
(:mod:`bioscientist_os.visualization.figures`) is an optional extra
(``pip install -e '.[viz]'``): when ``matplotlib`` is absent the data — written as
``results/figures/visualizations.json`` — is still produced, and figure-rendering
tests are skipped, so the core path stays light. The support/conflict signal and the
database links are heuristic / inferred respectively, never biological verdicts
(see ``docs/SAFETY.md``).
"""

from __future__ import annotations

from bioscientist_os.visualization.build import (
    build_cluster_summary,
    build_evidence_matrix,
    build_link_graph,
    build_support_conflict_table,
    build_timeline,
    build_visualization_report,
    load_visualizations,
)
from bioscientist_os.visualization.figures import (
    VisualizationArtifacts,
    matplotlib_available,
    render_figures,
    write_visualizations,
)
from bioscientist_os.visualization.model import (
    FIGURE_FILENAMES,
    MATRIX_CELL_VALUES,
    ClusterBar,
    ClusterSummary,
    EvidenceMatrix,
    GraphEdge,
    GraphNode,
    LinkGraph,
    SupportConflictRow,
    SupportConflictTable,
    TimelineSeries,
    VisualizationError,
    VisualizationReport,
)

__all__ = [
    # data model
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
    # builders
    "build_timeline",
    "build_cluster_summary",
    "build_evidence_matrix",
    "build_link_graph",
    "build_support_conflict_table",
    "build_visualization_report",
    "load_visualizations",
    # rendering / output
    "matplotlib_available",
    "VisualizationArtifacts",
    "render_figures",
    "write_visualizations",
]
