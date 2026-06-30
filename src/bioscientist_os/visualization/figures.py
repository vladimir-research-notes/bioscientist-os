"""Optional ``matplotlib`` rendering of the figure data (Milestone 7).

This module is the **only** part of the workbench that touches ``matplotlib``, and
it is an *optional* extra (``pip install -e '.[viz]'``). The import is lazy and
guarded: :func:`matplotlib_available` reports whether rendering is possible, and the
data layer (:mod:`bioscientist_os.visualization.build`) plus the JSON written by
:func:`write_visualizations` work with ``matplotlib`` absent, keeping the core test
path light. When ``matplotlib`` is missing the renderers raise
:class:`VisualizationError` and :func:`write_visualizations` simply skips the PNGs
(reporting that it did) while still writing ``visualizations.json``.

Only the figure *data* is guaranteed reproducible; PNG bytes can differ across
``matplotlib`` versions and fonts. The network graph layout is seeded so it is at
least visually stable run-to-run on the same machine. The non-interactive ``Agg``
backend is selected so rendering works headless (no display, no GUI).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bioscientist_os.visualization.model import (
    ClusterSummary,
    EvidenceMatrix,
    LinkGraph,
    SupportConflictTable,
    TimelineSeries,
    VisualizationError,
    VisualizationReport,
)

# Layout seed for the network graph, so a render is visually stable run-to-run.
_GRAPH_SEED = 7

# Colors for the support/conflict/unknown vocabulary, shared by the matrix and the
# support-conflict table. Deliberately not red/green only (color-blind-aware-ish):
# blue=support, orange=conflict, light grey=unknown, white=none.
_SUPPORT_COLORS: dict[str, str] = {
    "support": "#2c7fb8",
    "conflict": "#e6803c",
    "unknown": "#cfd4d9",
    "none": "#ffffff",
}
# Node colors for the link graph, by node kind.
_NODE_COLORS: dict[str, str] = {"entity": "#7fb3d5", "database": "#f5cba7"}


def matplotlib_available() -> bool:
    """True if ``matplotlib`` can be imported (the ``viz`` extra is installed)."""
    try:
        import matplotlib  # noqa: F401
    except Exception:  # pragma: no cover - exercised only without the extra
        return False
    return True


def _pyplot() -> Any:
    """Import pyplot with the headless ``Agg`` backend, or raise :class:`VisualizationError`."""
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless: no display required
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - exercised only without the extra
        raise VisualizationError(
            "matplotlib is required to render figures; install it with: "
            "pip install -e '.[viz]'  (the figure data is still written to "
            "visualizations.json without it)"
        ) from exc
    return plt


@dataclass(frozen=True)
class VisualizationArtifacts:
    """What :func:`write_visualizations` produced: the JSON path and any PNG paths."""

    json_path: Path
    figure_paths: dict[str, Path]
    rendered: bool
    matplotlib_available: bool

    def to_dict(self) -> dict:
        return {
            "json_path": str(self.json_path),
            "figure_paths": {k: str(v) for k, v in self.figure_paths.items()},
            "rendered": self.rendered,
            "matplotlib_available": self.matplotlib_available,
        }


# -- individual renderers --------------------------------------------------


def render_timeline(data: TimelineSeries, path: Path) -> Path:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if data.points:
        years = [y for y, _ in data.points]
        counts = [c for _, c in data.points]
        ax.bar([str(y) for y in years], counts, color="#5499c7")
        ax.set_ylim(0, max(counts) + 1)
    else:  # pragma: no cover - the fixture corpus always has dated papers
        ax.text(0.5, 0.5, "no dated papers", ha="center", va="center")
    ax.set_xlabel("publication year")
    ax.set_ylabel("papers")
    suffix = f"  ({data.undated} undated)" if data.undated else ""
    ax.set_title(f"Literature timeline — {data.total_papers} papers{suffix}")
    fig.text(0.01, 0.01, f"data_source={data.data_source}; {data.method}", fontsize=7, color="#555")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def render_cluster_summary(data: ClusterSummary, path: Path) -> Path:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = []
    sizes = []
    for b in data.bars:
        head = b.label_terms[0] if b.label_terms else ""
        labels.append(f"{b.topic_id} ({head})" if head else b.topic_id)
        sizes.append(b.size)
    y = list(range(len(labels)))
    ax.barh(y, sizes, color="#48a999")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()  # largest group on top
    ax.set_xlabel("papers in group")
    ax.set_title(
        f"Topic clusters — {data.num_groups} groups "
        f"({data.num_singletons} singleton), threshold={data.threshold}"
    )
    fig.text(0.01, 0.01, f"data_source={data.data_source}; {data.method}", fontsize=7, color="#555")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def render_evidence_matrix(data: EvidenceMatrix, path: Path) -> Path:
    plt = _pyplot()
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    # Encode cell labels to integer codes for an imshow grid.
    codes = {"none": 0, "unknown": 1, "support": 2, "conflict": 3}
    cmap = ListedColormap(
        [
            _SUPPORT_COLORS["none"],
            _SUPPORT_COLORS["unknown"],
            _SUPPORT_COLORS["support"],
            _SUPPORT_COLORS["conflict"],
        ]
    )
    nrows = max(len(data.paper_ids), 1)
    ncols = max(len(data.entity_names), 1)
    grid = [[codes.get(v, 0) for v in row] for row in data.cells] or [[0]]

    fig, ax = plt.subplots(figsize=(max(6, ncols * 1.1), max(4, nrows * 0.5)))
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(data.entity_names)))
    ax.set_xticklabels(data.entity_names, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(data.paper_ids)))
    ax.set_yticklabels(data.paper_ids, fontsize=8)
    ax.set_title(f"Evidence matrix — {data.question_id}", fontsize=10)
    legend = [
        Patch(facecolor=_SUPPORT_COLORS[k], edgecolor="#888", label=k)
        for k in ("support", "conflict", "unknown", "none")
    ]
    ax.legend(handles=legend, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7)
    fig.text(
        0.01, 0.01,
        "heuristic textual signal, NOT a biological verdict; "
        f"data_source={data.data_source}",
        fontsize=7, color="#a33",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def render_link_graph(data: LinkGraph, path: Path) -> Path:
    plt = _pyplot()
    import networkx as nx

    graph: nx.Graph = nx.Graph()
    for n in data.nodes:
        graph.add_node(n.node_id, kind=n.kind)
    for e in data.edges:
        graph.add_edge(e.source, e.target, kind=e.kind)

    pos = nx.spring_layout(graph, seed=_GRAPH_SEED, k=0.6)
    fig, ax = plt.subplots(figsize=(10, 8))

    by_kind: dict[str, list[str]] = {"entity": [], "database": []}
    labels: dict[str, str] = {}
    for n in data.nodes:
        by_kind.setdefault(n.kind, []).append(n.node_id)
        labels[n.node_id] = n.label
    for kind, ids in by_kind.items():
        nx.draw_networkx_nodes(
            graph, pos, nodelist=ids, node_color=_NODE_COLORS.get(kind, "#cccccc"),
            node_size=[200 + 60 * graph.degree(i) for i in ids], ax=ax, label=kind,
        )
    edge_styles = {"co-occurrence": "solid", "xref": "dashed", "association": "dotted"}
    for kind, style in edge_styles.items():
        elist = [(e.source, e.target) for e in data.edges if e.kind == kind]
        if elist:
            nx.draw_networkx_edges(
                graph, pos, edgelist=elist, style=style, edge_color="#999", ax=ax
            )
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=6, ax=ax)
    ax.set_title(
        f"Entity / database-link graph — {len(data.nodes)} nodes, {len(data.edges)} edges"
    )
    ax.legend(scatterpoints=1, fontsize=8, loc="upper left")
    ax.axis("off")
    fig.text(
        0.01, 0.01,
        "edges are inferred relations (db-xrefs + associations) and claim "
        f"co-occurrence, not biological claims; data_source={data.data_source}",
        fontsize=7, color="#555",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def render_support_conflict(data: SupportConflictTable, path: Path) -> Path:
    plt = _pyplot()
    header = ["research question", "support", "conflict", "unknown", "total"]
    body = []
    for r in data.rows:
        body.append([r.question_id, r.support, r.conflict, r.unknown, r.total])
    t = data.totals()
    body.append(["TOTAL", t["support"], t["conflict"], t["unknown"], t["total"]])

    fig, ax = plt.subplots(figsize=(9, 0.6 + 0.5 * (len(body) + 1)))
    ax.axis("off")
    table = ax.table(cellText=body, colLabels=header, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)
    # Tint the support / conflict / unknown columns to echo the matrix legend.
    for col, key in ((1, "support"), (2, "conflict"), (3, "unknown")):
        for row in range(1, len(body) + 1):
            table[row, col].set_facecolor(_SUPPORT_COLORS[key])
    ax.set_title("Support vs. conflict per research question", fontsize=11)
    fig.text(
        0.01, 0.01,
        "heuristic textual counts, NOT biological verdicts; "
        f"data_source={data.data_source}",
        fontsize=7, color="#a33",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


# -- orchestration ---------------------------------------------------------

_RENDERERS = {
    "timeline": render_timeline,
    "topic_clusters": render_cluster_summary,
    "evidence_matrix": render_evidence_matrix,
    "link_graph": render_link_graph,
    "support_conflict": render_support_conflict,
}


def render_figures(report: VisualizationReport, out_dir: str | Path) -> dict[str, Path]:
    """Render all five figures to ``out_dir`` (requires ``matplotlib``).

    Returns ``{figure_key: png_path}``. Raises :class:`VisualizationError` if
    ``matplotlib`` is not installed.
    """
    if not matplotlib_available():
        raise VisualizationError(
            "matplotlib is not installed; install the viz extra (pip install -e '.[viz]') "
            "to render figures, or use write_visualizations() to emit the data only"
        )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    figures = report.figures()
    for key, filename in report_filenames(report).items():
        renderer = _RENDERERS[key]
        paths[key] = renderer(figures[key], out / filename)
    return paths


def report_filenames(report: VisualizationReport) -> dict[str, str]:
    """The ``{figure_key: filename}`` mapping for a report (stable order)."""
    from bioscientist_os.visualization.model import FIGURE_FILENAMES

    return {key: FIGURE_FILENAMES[key] for key in report.FIGURE_KEYS}


def write_visualizations(
    report: VisualizationReport,
    out_dir: str | Path,
    *,
    render: bool = True,
    json_name: str = "visualizations.json",
) -> VisualizationArtifacts:
    """Write the figure data JSON (always) and, if possible, render the PNGs.

    ``visualizations.json`` — the inspectable figure data — is written unconditionally
    so the chain survives on the light core path. PNGs are rendered only when
    ``render`` is true *and* ``matplotlib`` is installed; otherwise they are skipped
    and the returned :class:`VisualizationArtifacts` records that honestly.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / json_name
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )

    available = matplotlib_available()
    figure_paths: dict[str, Path] = {}
    rendered = False
    if render and available:
        figure_paths = render_figures(report, out)
        rendered = True
    return VisualizationArtifacts(
        json_path=json_path,
        figure_paths=figure_paths,
        rendered=rendered,
        matplotlib_available=available,
    )


__all__ = [
    "matplotlib_available",
    "VisualizationArtifacts",
    "render_timeline",
    "render_cluster_summary",
    "render_evidence_matrix",
    "render_link_graph",
    "render_support_conflict",
    "render_figures",
    "write_visualizations",
]
