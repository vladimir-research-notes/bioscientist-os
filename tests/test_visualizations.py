"""Tests for the workbench visualizations (Milestone 7).

The milestone calls for five figures — a literature timeline, a topic-cluster
summary, a claim/evidence matrix, an entity/database-link graph, and a
support-vs-conflict table — saved under ``results/figures/``, with figure-rendering
tests skipped when ``matplotlib`` is absent so the core path stays light.

The emphasis here matches the project's discipline: the figure **data** is a pure,
deterministic, provenance-carrying re-presentation of the workbench's own reports,
and it is tested unconditionally (no ``matplotlib`` needed). The PNG **rendering**
is an optional skin, tested only when the ``viz`` extra is installed. Two epistemic
guards are asserted explicitly: the evidence matrix and the support-conflict table
both carry the "heuristic textual signal, not a biological verdict" framing, and the
link graph's database edges are labeled inferred relations. Everything runs offline
from the committed fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.evidence import build_dictionary, build_evidence_report, extract_corpus
from bioscientist_os.evidence.dictionary import EntityDictionary
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.evidence.table import EvidenceReport
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import DatabaseRecord, Paper, ResearchQuestion
from bioscientist_os.search import SearchIndex, group_topics
from bioscientist_os.visualization import (
    FIGURE_FILENAMES,
    MATRIX_CELL_VALUES,
    VisualizationError,
    VisualizationReport,
    build_cluster_summary,
    build_evidence_matrix,
    build_link_graph,
    build_support_conflict_table,
    build_timeline,
    build_visualization_report,
    matplotlib_available,
    render_figures,
    write_visualizations,
)

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> fixtures.FixtureBundle:
    return fixtures.load_all()


@pytest.fixture(scope="module")
def records(bundle: fixtures.FixtureBundle) -> list[DatabaseRecord]:
    return bundle.proteins + bundle.associations


@pytest.fixture(scope="module")
def papers(bundle: fixtures.FixtureBundle) -> list[Paper]:
    return bundle.papers


@pytest.fixture(scope="module")
def questions(bundle: fixtures.FixtureBundle) -> list[ResearchQuestion]:
    return bundle.questions


@pytest.fixture(scope="module")
def dictionary(records: list[DatabaseRecord]) -> EntityDictionary:
    return build_dictionary(records)


@pytest.fixture(scope="module")
def extraction(papers: list[Paper], dictionary: EntityDictionary) -> ExtractionReport:
    return extract_corpus(papers, dictionary)


@pytest.fixture(scope="module")
def report(
    papers: list[Paper], records: list[DatabaseRecord], questions: list[ResearchQuestion]
) -> VisualizationReport:
    return build_visualization_report(papers, records, questions)


def _evidence(
    qid: str,
    questions: list[ResearchQuestion],
    extraction: ExtractionReport,
    dictionary: EntityDictionary,
    records: list[DatabaseRecord],
) -> EvidenceReport:
    q = next(q for q in questions if q.question_id == qid)
    return build_evidence_report(q, extraction, dictionary, records)


# --- literature timeline --------------------------------------------------


def test_timeline_counts_papers_by_year(papers: list[Paper]) -> None:
    tl = build_timeline(papers)
    assert tl.total_papers == len(papers)
    assert tl.undated == sum(1 for p in papers if p.year is None)
    # the per-year counts (plus undated) account for every paper, exactly once
    assert sum(c for _, c in tl.points) + tl.undated == len(papers)
    # points are sorted ascending by year and reference real fixture years
    years = [y for y, _ in tl.points]
    assert years == sorted(years)
    assert set(years) == {p.year for p in papers if p.year is not None}
    assert tl.data_source == "fixture"


# --- topic-cluster summary ------------------------------------------------


def test_cluster_summary_matches_topic_report(papers: list[Paper]) -> None:
    index = SearchIndex.from_papers(papers)
    cl = build_cluster_summary(index)
    topic_report = group_topics(index)
    assert cl.num_groups == topic_report.num_groups
    assert cl.num_singletons == topic_report.num_singletons
    # every paper lands in exactly one group, so the bar sizes sum to the corpus
    assert sum(b.size for b in cl.bars) == len(papers)
    # the topic report orders groups largest-first; the summary preserves that
    sizes = [b.size for b in cl.bars]
    assert sizes == sorted(sizes, reverse=True)


# --- claim / evidence matrix ----------------------------------------------


def test_evidence_matrix_shape_and_cell_vocabulary(
    questions, extraction, dictionary, records
) -> None:
    ev = _evidence("rq-senescence-inflammation", questions, extraction, dictionary, records)
    mx = build_evidence_matrix(ev)
    # columns are exactly the question entities; rows are the contributing papers
    assert mx.entity_names == ev.question_entity_names
    assert set(mx.paper_ids) <= {r.paper_id for r in ev.rows}
    assert mx.paper_ids == sorted(mx.paper_ids)
    # the grid is rectangular and every cell uses the declared vocabulary
    assert mx.shape == (len(mx.paper_ids), len(mx.entity_names))
    for row in mx.cells:
        assert len(row) == len(mx.entity_names)
        assert all(v in MATRIX_CELL_VALUES for v in row)
    counts = mx.cell_counts()
    assert sum(counts.values()) == mx.shape[0] * mx.shape[1]
    # the senescence-inflammation table exercises both support and conflict cells
    assert counts["support"] > 0 and counts["conflict"] > 0
    # epistemic guard: the cell is a textual signal, never a biological verdict
    assert "NOT a biological" in mx.caption


def test_evidence_matrix_cell_is_highest_confidence_label(
    questions, extraction, dictionary, records
) -> None:
    ev = _evidence("rq-senescence-inflammation", questions, extraction, dictionary, records)
    mx = build_evidence_matrix(ev)
    # Independently recompute the strongest label for each (paper, entity) and compare.
    best: dict[tuple[str, str], tuple[float, str, str]] = {}
    for r in ev.rows:
        for ename in ev.question_entity_names:
            if ename in r.entity_names:
                key = (r.paper_id, ename)
                cand = (r.confidence, r.claim_id, r.support_conflict_unknown.value)
                cur = best.get(key)
                if cur is None or cand[0] > cur[0] or (cand[0] == cur[0] and cand[1] < cur[1]):
                    best[key] = cand
    for i, pid in enumerate(mx.paper_ids):
        for j, ename in enumerate(mx.entity_names):
            expected = best.get((pid, ename), (0.0, "", "none"))[2]
            assert mx.cells[i][j] == expected


# --- entity / database-link graph -----------------------------------------


def test_link_graph_has_entities_and_database_links(extraction, dictionary, records) -> None:
    lg = build_link_graph(extraction, dictionary, records)
    node_ids = {n.node_id for n in lg.nodes}
    assert "ent-IL6" in node_ids
    # the IL-6 entity's xrefs and Open Targets association are database nodes/edges
    assert {"UniProt:P05231", "HGNC:IL6", "OpenTargets:OTAF-0002"} <= node_ids
    il6_links = {
        e.target for e in lg.edges if e.source == "ent-IL6" and e.kind in ("xref", "association")
    }
    assert {"UniProt:P05231", "HGNC:IL6", "OpenTargets:OTAF-0002"} <= il6_links
    # entity nodes carry their coarse type; database nodes do not
    il6 = next(n for n in lg.nodes if n.node_id == "ent-IL6")
    assert il6.kind == "entity" and il6.entity_type == "protein"


def test_link_graph_edges_are_consistent(extraction, dictionary, records) -> None:
    lg = build_link_graph(extraction, dictionary, records)
    node_ids = {n.node_id for n in lg.nodes}
    # every edge endpoint is a real node; co-occurrence edges are entity↔entity, ordered
    entity_ids = {n.node_id for n in lg.nodes if n.kind == "entity"}
    for e in lg.edges:
        assert e.source in node_ids and e.target in node_ids
        if e.kind == "co-occurrence":
            assert e.source in entity_ids and e.target in entity_ids
            assert e.source < e.target  # undirected, stored in a stable order
        else:
            assert e.source in entity_ids  # xref/association start at an entity
    # each node's recorded degree equals its incident-edge count
    incident: dict[str, int] = {n.node_id: 0 for n in lg.nodes}
    for e in lg.edges:
        incident[e.source] += 1
        incident[e.target] += 1
    for n in lg.nodes:
        assert n.degree == incident[n.node_id]
    # counts agree with the node/edge lists
    assert sum(lg.node_counts().values()) == len(lg.nodes)
    assert sum(lg.edge_counts().values()) == len(lg.edges)


# --- support-vs-conflict table --------------------------------------------


def test_support_conflict_table_matches_evidence_reports(
    questions, extraction, dictionary, records
) -> None:
    reports = [
        build_evidence_report(q, extraction, dictionary, records) for q in questions
    ]
    table = build_support_conflict_table(reports)
    assert len(table.rows) == len(reports)
    for row, ev in zip(table.rows, reports, strict=True):
        counts = ev.support_counts()
        assert (row.support, row.conflict, row.unknown) == (
            counts["support"], counts["conflict"], counts["unknown"]
        )
        assert row.total == ev.num_rows
    totals = table.totals()
    assert totals["total"] == sum(r.total for r in table.rows)
    # epistemic guard
    assert "never a biological" in table.caption


# --- the assembled report -------------------------------------------------


def test_report_has_all_five_figures(report: VisualizationReport) -> None:
    figs = report.figures()
    assert set(figs) == set(FIGURE_FILENAMES)
    assert set(report.FIGURE_KEYS) == set(FIGURE_FILENAMES)
    # default matrix question is the first stored question, recorded in params
    assert report.params["primary_question_id"] == report.matrix.question_id


def test_report_to_dict_is_json_serializable_and_deterministic(
    papers, records, questions
) -> None:
    a = json.dumps(build_visualization_report(papers, records, questions).to_dict(), sort_keys=True)
    b = json.dumps(build_visualization_report(papers, records, questions).to_dict(), sort_keys=True)
    assert a == b
    payload = json.loads(a)
    assert set(payload["figures"]) == set(FIGURE_FILENAMES)


def test_primary_question_selectable(papers, records, questions) -> None:
    rep = build_visualization_report(
        papers, records, questions, question_id="rq-senescence-inflammation"
    )
    assert rep.matrix.question_id == "rq-senescence-inflammation"


# --- output: data always, PNGs only with matplotlib -----------------------


def test_write_visualizations_always_writes_json(report, tmp_path: Path) -> None:
    artifacts = write_visualizations(report, tmp_path, render=False)
    assert artifacts.json_path.is_file()
    assert artifacts.rendered is False
    assert artifacts.figure_paths == {}
    # the JSON on disk is the report's data
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert set(payload["figures"]) == set(FIGURE_FILENAMES)


def test_write_visualizations_render_flag_matches_availability(report, tmp_path: Path) -> None:
    artifacts = write_visualizations(report, tmp_path, render=True)
    # JSON is written regardless; PNGs only when matplotlib is importable
    assert artifacts.json_path.is_file()
    assert artifacts.matplotlib_available == matplotlib_available()
    assert artifacts.rendered == matplotlib_available()


@pytest.mark.skipif(matplotlib_available(), reason="matplotlib installed; guard not triggered")
def test_render_figures_raises_without_matplotlib(report, tmp_path: Path) -> None:
    with pytest.raises(VisualizationError):
        render_figures(report, tmp_path)


@pytest.mark.skipif(not matplotlib_available(), reason="matplotlib (viz extra) not installed")
def test_render_writes_five_nonempty_pngs(report, tmp_path: Path) -> None:
    paths = render_figures(report, tmp_path)
    assert set(paths) == set(FIGURE_FILENAMES)
    for key, filename in FIGURE_FILENAMES.items():
        png = paths[key]
        assert png.name == filename
        data = png.read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")  # valid PNG magic
        assert len(data) > 1000


# --- CLI ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("figurescli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


def test_cli_figures_json(cli_db: Path) -> None:
    res = runner.invoke(app, ["figures", "--db", str(cli_db), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert set(payload["figures"]) == set(FIGURE_FILENAMES)


def test_cli_figures_writes_json_artifact(cli_db: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "figs"
    res = runner.invoke(app, ["figures", "--db", str(cli_db), "--out-dir", str(out_dir)])
    assert res.exit_code == 0, res.output
    assert (out_dir / "visualizations.json").is_file()
    assert "heuristic textual signal" in res.output  # safety framing in the footer
    if matplotlib_available():
        for filename in FIGURE_FILENAMES.values():
            assert (out_dir / filename).is_file()
    else:
        assert "matplotlib not installed" in res.output


def test_cli_figures_no_render(cli_db: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "figs_norender"
    res = runner.invoke(
        app, ["figures", "--db", str(cli_db), "--out-dir", str(out_dir), "--no-render"]
    )
    assert res.exit_code == 0, res.output
    assert (out_dir / "visualizations.json").is_file()
    assert not any(out_dir.glob("*.png"))
    assert "--no-render" in res.output


def test_cli_figures_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["figures", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
