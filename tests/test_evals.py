"""Tests for the self-evaluation harness (Milestone 8).

Cover what the milestone calls for: ingestion correctness, search recall on
hand-labeled queries, entity precision/recall against tiny gold labels, claim
sanity, evidence-table completeness, and provenance coverage — each reported as a
:class:`Proportion` with an explicit denominator and a Wilson interval. The
emphasis is on the project's disciplines: honest denominators (no bare
percentages), intervals that bracket the estimate, deliberate recall *misses*
surfaced rather than hidden, and full determinism. Everything runs offline from the
committed fixtures and the committed gold labels.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.evals import (
    GoldError,
    GoldQuery,
    Proportion,
    evaluate_claims,
    evaluate_entities,
    evaluate_evidence,
    evaluate_ingestion,
    evaluate_search_recall,
    f1_score,
    load_gold,
    run_eval,
    wilson_interval,
    z_for_confidence,
)
from bioscientist_os.evals.metrics import DEFAULT_CONFIDENCE
from bioscientist_os.evidence import build_dictionary, extract_corpus
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.search import SearchIndex

runner = CliRunner()


# --- shared fixtures ------------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> fixtures.FixtureBundle:
    return fixtures.load_all()


@pytest.fixture(scope="module")
def dictionary(bundle):
    return build_dictionary(bundle.proteins + bundle.associations)


@pytest.fixture(scope="module")
def extraction(bundle, dictionary):
    return extract_corpus(bundle.papers, dictionary)


@pytest.fixture(scope="module")
def papers_by_id(bundle):
    return {p.paper_id: p for p in bundle.papers}


@pytest.fixture(scope="module")
def gold():
    return load_gold()


@pytest.fixture(scope="module")
def eval_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("evaldb") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


# --- metrics: Wilson interval + Proportion --------------------------------


def test_z_for_confidence_95() -> None:
    assert z_for_confidence(0.95) == pytest.approx(1.959963984540054)
    assert z_for_confidence(0.90) < z_for_confidence(0.99)


def test_wilson_interval_brackets_point_and_stays_in_unit() -> None:
    low, high = wilson_interval(14, 16)
    assert 0.0 <= low <= 14 / 16 <= high <= 1.0
    # known reference values for 22/24 at 95%
    lo2, hi2 = wilson_interval(22, 24)
    assert lo2 == pytest.approx(0.742, abs=0.01)
    assert hi2 == pytest.approx(0.977, abs=0.01)


def test_wilson_interval_edges_are_well_behaved() -> None:
    # n == 0 -> maximally uncertain, never a misleading 0%
    assert wilson_interval(0, 0) == (0.0, 1.0)
    # k == 0 and k == n give non-degenerate one-sided intervals (unlike Wald)
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == pytest.approx(0.0, abs=1e-9) and 0.0 < hi0 < 1.0
    lon, hin = wilson_interval(10, 10)
    assert hin == pytest.approx(1.0, abs=1e-9) and 0.0 < lon < 1.0


def test_wilson_interval_rejects_bad_counts() -> None:
    with pytest.raises(ValueError):
        wilson_interval(5, 3)
    with pytest.raises(ValueError):
        wilson_interval(-1, 3)


def test_proportion_point_is_none_for_empty_denominator() -> None:
    p = Proportion("x", 0, 0)
    assert p.point is None
    d = p.to_dict()
    assert d["denominator"] == 0 and d["point_estimate"] is None
    assert "0/0" in p.format_line()


def test_proportion_to_dict_carries_denominator_and_interval() -> None:
    p = Proportion("recall@3", 14, 16)
    d = p.to_dict()
    assert d["numerator"] == 14 and d["denominator"] == 16
    assert d["point_estimate"] == pytest.approx(0.875)
    assert d["ci_low"] <= 0.875 <= d["ci_high"]
    assert d["interval_method"] == "wilson"
    assert d["confidence_level"] == DEFAULT_CONFIDENCE


def test_f1_score() -> None:
    assert f1_score(1.0, 0.917) == pytest.approx(2 * 0.917 / (1.0 + 0.917), abs=1e-6)
    assert f1_score(None, 0.5) is None
    assert f1_score(0.0, 0.0) == 0.0


# --- gold labels ----------------------------------------------------------


def test_gold_loads_expected_counts(gold) -> None:
    s = gold.summary()
    assert s["queries"] == 6
    assert s["relevant_pairs"] == 16
    assert s["entity_labeled_abstracts"] == 6
    assert s["gold_entity_mentions"] == 24


def test_gold_modeled_flag_matches_live_dictionary(gold, dictionary) -> None:
    # The committed `modeled` flag must agree with what the dictionary can recognize,
    # so a drift between the labels and the dictionary is caught.
    for label in gold.entity_labels:
        for e in label.gold_entities:
            assert e.modeled == (e.entity_id in dictionary.entities), (
                f"{label.paper_id}/{e.entity_id}: modeled flag disagrees with dictionary"
            )


def test_gold_query_relevant_ids_exist_in_corpus(gold, papers_by_id) -> None:
    for q in gold.queries:
        for pid in q.relevant_paper_ids:
            assert pid in papers_by_id


def test_gold_loader_reports_malformed_file(tmp_path) -> None:
    (tmp_path / "search_queries.json").write_text("{}", encoding="utf-8")  # not an array
    (tmp_path / "entity_labels.json").write_text("[]", encoding="utf-8")
    with pytest.raises(GoldError):
        load_gold(tmp_path)


# --- ingestion correctness ------------------------------------------------


def test_ingestion_correctness_all_round_trip(bundle, eval_db) -> None:
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(eval_db) as store:
        papers = list(store.iter_papers())
        records = list(store.iter_database_records())
        questions = list(store.iter_research_questions())
    result = evaluate_ingestion(bundle, papers, records, questions)
    assert result.overall.numerator == result.overall.denominator == 40
    assert result.overall.point == 1.0
    assert result.papers.numerator == 18
    assert result.database_records.numerator == 19  # 10 proteins + 9 associations
    assert result.research_questions.numerator == 3
    assert result.extra_in_db == {"papers": 0, "database_records": 0, "research_questions": 0}
    assert result.mismatched_ids["papers"] == []


def test_ingestion_correctness_detects_a_missing_row(bundle, eval_db) -> None:
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(eval_db) as store:
        papers = list(store.iter_papers())[:-1]  # drop one ingested paper
        records = list(store.iter_database_records())
        questions = list(store.iter_research_questions())
    result = evaluate_ingestion(bundle, papers, records, questions)
    assert result.papers.numerator == 17 and result.papers.denominator == 18
    assert result.overall.numerator == 39 and result.overall.denominator == 40


# --- search recall --------------------------------------------------------


def test_search_recall_on_gold_queries(bundle, gold) -> None:
    index = SearchIndex.from_papers(bundle.papers)
    result = evaluate_search_recall(index, list(gold.queries), recall_k=(3, 5))
    by_k = {int(p.label.split("@")[1]): p for p in result.recall_micro}
    assert by_k[3].numerator == 14 and by_k[3].denominator == 16  # two relevant just outside top-3
    assert by_k[5].numerator == 16 and by_k[5].denominator == 16  # all recovered by k=5
    assert result.recall_macro[5] == pytest.approx(1.0)
    # recall is non-decreasing in k
    assert by_k[3].point <= by_k[5].point


def test_search_recall_per_query_records_ranks(bundle, gold) -> None:
    index = SearchIndex.from_papers(bundle.papers)
    result = evaluate_search_recall(index, list(gold.queries), recall_k=(3, 5))
    detail = {d["query_id"]: d for d in result.per_query}
    foxo3 = detail["q-foxo3-longevity"]
    assert foxo3["num_relevant"] == 1
    assert foxo3["relevant_ranks"]["biosci-paper-011"] == 1  # single-target, top hit
    # the deliberately-hard relevant paper for the marker query is outside top-3
    marker = detail["q-senescence-marker-p16"]
    assert marker["relevant_ranks"]["biosci-paper-016"] is None or marker["recall_at_k"]["3"] < 1.0


def test_search_recall_rejects_unknown_gold_paper(bundle) -> None:
    index = SearchIndex.from_papers(bundle.papers)
    bad = GoldQuery("q-bad", "senescence", ("biosci-paper-999",))
    with pytest.raises(ValueError):
        evaluate_search_recall(index, [bad])


# --- entity precision / recall --------------------------------------------


def test_entity_precision_recall_against_gold(papers_by_id, dictionary, gold) -> None:
    result = evaluate_entities(papers_by_id, dictionary, list(gold.entity_labels))
    assert result.precision.numerator == 22 and result.precision.denominator == 22  # no FPs
    assert result.recall.numerator == 22 and result.recall.denominator == 24  # 2 FNs
    assert result.false_negatives == 2 and result.false_positives == 0
    assert result.f1 == pytest.approx(f1_score(1.0, 22 / 24))


def test_entity_recall_misses_are_the_documented_ones(papers_by_id, dictionary, gold) -> None:
    result = evaluate_entities(papers_by_id, dictionary, list(gold.entity_labels))
    by_paper = {d["paper_id"]: d for d in result.per_abstract}
    # IL-8 has no fixture record -> unrecognizable (paper-001)
    assert "ent-IL8" in by_paper["biosci-paper-001"]["false_negatives"]
    # p16INK4a-expressing is one hyphenated token -> CDKN2A missed (paper-003)
    assert "ent-CDKN2A" in by_paper["biosci-paper-003"]["false_negatives"]
    # a clean abstract has no misses
    assert by_paper["biosci-paper-002"]["false_negatives"] == []


# --- claim sanity ---------------------------------------------------------


def test_claim_sanity_all_well_formed_and_traceable(extraction, papers_by_id, dictionary) -> None:
    result = evaluate_claims(extraction, papers_by_id, dictionary)
    assert result.num_claims == 42
    assert result.num_relations == 15
    assert result.overall.numerator == result.overall.denominator == 42
    # every individual check passes for every claim (a regression floor)
    for name, p in result.per_check.items():
        assert p.numerator == 42, f"check {name} failed for some claim"
    # the span-round-trip check is the substantive traceability guarantee
    assert result.per_check["span_round_trips"].numerator == 42


# --- evidence completeness + provenance -----------------------------------


def test_evidence_completeness_and_provenance(bundle, extraction, dictionary) -> None:
    records = bundle.proteins + bundle.associations
    result = evaluate_evidence(bundle.questions, extraction, dictionary, records)
    assert result.total_rows == 68
    assert result.completeness.numerator == result.completeness.denominator == 68
    assert result.provenance_coverage.numerator == 68
    assert len(result.per_question) == 3
    # per-question row counts sum to the total
    assert sum(q["num_rows"] for q in result.per_question) == 68
    for q in result.per_question:
        assert q["complete_rows"] == q["num_rows"]
        assert q["full_provenance_rows"] == q["num_rows"]


# --- end-to-end run_eval --------------------------------------------------


def test_run_eval_end_to_end(eval_db) -> None:
    report = run_eval(eval_db)
    assert report.data_source == "fixture"
    assert report.ingestion.overall.point == 1.0
    assert report.entities.recall.numerator == 22
    assert report.evidence.total_rows == 68
    # headline carries every section's key proportion
    assert len(report.headline()) >= 7
    # the report is JSON-serializable as produced
    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["entities"]["false_negatives"] == 2


def test_run_eval_is_deterministic(eval_db) -> None:
    first = run_eval(eval_db).to_dict()
    second = run_eval(eval_db).to_dict()
    assert first == second


def test_run_eval_on_uninitialized_db_errors(tmp_path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    with pytest.raises(ValueError, match="not a bioscientist-os database"):
        run_eval(empty)


def test_run_eval_confidence_widens_interval(eval_db) -> None:
    narrow = run_eval(eval_db, confidence=0.80).entities.recall.ci
    wide = run_eval(eval_db, confidence=0.99).entities.recall.ci
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


# --- CLI ------------------------------------------------------------------


def test_cli_eval_text_output(eval_db) -> None:
    res = runner.invoke(app, ["eval", "--db", str(eval_db)])
    assert res.exit_code == 0, res.output
    assert "Self-evaluation" in res.output
    assert "Ingestion correctness" in res.output
    assert "recall@3" in res.output
    assert "Wilson" in res.output
    assert "biological truth" in res.output  # safety framing present
    assert "docs/SAFETY.md" in res.output


def test_cli_eval_json_and_out(eval_db, tmp_path) -> None:
    out = tmp_path / "sub" / "eval_report.json"
    res = runner.invoke(app, ["eval", "--db", str(eval_db), "--out", str(out), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ingestion"]["overall"]["denominator"] == 40
    assert payload["evidence"]["total_rows"] == 68
    # the JSON file was written (parent dirs created)
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["method"] == payload["method"]


def test_cli_eval_bad_confidence_errors(eval_db) -> None:
    res = runner.invoke(app, ["eval", "--db", str(eval_db), "--confidence", "1.5"])
    assert res.exit_code == 2
    assert "confidence" in res.output


def test_cli_eval_on_uninitialized_db_errors(tmp_path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["eval", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
