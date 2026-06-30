"""Tests for CPU-only search and topic grouping (Milestone 3).

Cover what the milestone calls for: a lexical (BM25F) baseline, an optional TF-IDF
cosine mode, simple topic grouping, and a per-result *explanation* of which terms
and fields matched. Includes tiny labeled queries (expected paper in the top
results), score/explanation invariants, determinism, clustering properties, and
the ``biosci search`` / ``biosci topics`` CLI. Everything runs offline from the
committed fixtures or a tiny in-test corpus.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import DataSource, Paper
from bioscientist_os.search import SearchIndex, group_topics
from bioscientist_os.search.tokenize import bm25_idf, content_tokens, tokenize
from bioscientist_os.search.topics import DEFAULT_THRESHOLD

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def index() -> SearchIndex:
    """A SearchIndex over the committed fixture corpus (built once per module)."""
    return SearchIndex.from_papers(fixtures.load_all().papers)


def _paper(pid: str, title: str, *, keywords=None, abstract: str = "") -> Paper:
    return Paper(
        paper_id=pid, title=title, keywords=keywords or [], abstract=abstract,
        data_source=DataSource.fixture, synthetic=True,
    )


# --- tokenizer ------------------------------------------------------------


def test_tokenizer_lowercases_and_keeps_internal_hyphens() -> None:
    assert tokenize("Senescent fibroblasts secrete IL-6 and IL-8") == [
        "senescent", "fibroblasts", "secrete", "il-6", "and", "il-8",
    ]
    # mixed-case identifiers fold to lowercase; standalone punctuation drops out
    assert tokenize("p16INK4a, p53; ATG7-dependent.") == ["p16ink4a", "p53", "atg7-dependent"]


def test_tokenizer_distinguishes_hyphenated_from_joined() -> None:
    # Search does not unify surface forms; IL-6 and IL6 are different tokens.
    assert tokenize("IL-6") == ["il-6"]
    assert tokenize("IL6") == ["il6"]


def test_content_tokens_drop_stopwords_and_pure_digits() -> None:
    toks = content_tokens("We observed that IL-6 increased in 2008 with the senescence program")
    assert "il-6" in toks and "senescence" in toks and "program" in toks
    assert "we" not in toks and "the" not in toks and "that" not in toks
    assert "2008" not in toks  # pure-digit token removed


# --- BM25F scoring + explanation ------------------------------------------


def test_score_equals_sum_of_term_contributions(index: SearchIndex) -> None:
    response = index.search("autophagy senescence il-6 zzznotacorpusterm", limit=20)
    assert response.hits
    for hit in response.hits:
        total = sum(m.contribution for m in hit.term_matches)
        assert math.isclose(total, hit.score, rel_tol=1e-9, abs_tol=1e-12)


def test_unmatched_query_term_is_reported_with_zero_contribution(index: SearchIndex) -> None:
    response = index.search("senescence zzznotacorpusterm", limit=5)
    top = response.hits[0]
    by_term = {m.term: m for m in top.term_matches}
    assert by_term["zzznotacorpusterm"].matched is False
    assert by_term["zzznotacorpusterm"].contribution == 0.0
    assert by_term["zzznotacorpusterm"].idf == 0.0  # term absent from the corpus
    assert by_term["senescence"].matched is True
    assert by_term["senescence"].contribution > 0.0


def test_matched_fields_and_why_reflect_actual_fields(index: SearchIndex) -> None:
    # "rapamycin" is a keyword and appears in paper-004's abstract, but its title
    # reads "Rapamycin-mediated ..." which tokenizes to the single hyphenated token
    # "rapamycin-mediated" — so the bare term does NOT match the title. The reported
    # fields reflect exactly that (a faithful demonstration of the tokenizer's
    # documented hyphen behavior).
    response = index.search("rapamycin", limit=1)
    hit = response.hits[0]
    assert hit.paper_id == "biosci-paper-004"
    assert hit.matched_fields == ["abstract", "keywords"]
    assert "rapamycin[abstract,keywords]" in hit.why()
    # The hyphenated surface form is what matches the title.
    assert "title" in index.search("rapamycin-mediated", limit=1).hits[0].matched_fields


def test_field_weighting_prefers_title_over_abstract_only() -> None:
    # Two papers, same single matching token, but one has it in the (heavier) title.
    idx = SearchIndex.from_papers([
        _paper("p-title", "autophagy", abstract="unrelated body text here"),
        _paper("p-abs", "unrelated heading", abstract="the autophagy pathway is discussed"),
    ])
    hits = {h.paper_id: h.score for h in idx.search("autophagy").hits}
    assert hits["p-title"] > hits["p-abs"]


def test_ranking_is_deterministic_and_tie_broken_by_paper_id() -> None:
    # Two papers with identical text get identical scores; order falls back to id.
    idx = SearchIndex.from_papers([
        _paper("p-b", "senescence", abstract="senescence"),
        _paper("p-a", "senescence", abstract="senescence"),
    ])
    r1 = idx.search("senescence")
    r2 = idx.search("senescence")
    assert [h.paper_id for h in r1.hits] == [h.paper_id for h in r2.hits]
    assert [h.score for h in r1.hits] == [h.score for h in r2.hits]
    assert r1.hits[0].paper_id == "p-a"  # tie -> ascending paper_id
    assert r1.hits[0].rank == 1 and r1.hits[1].rank == 2


def test_limit_caps_hits_and_empty_query_returns_nothing(index: SearchIndex) -> None:
    assert len(index.search("senescence autophagy il-6", limit=3).hits) == 3
    assert index.search("").hits == []
    assert index.search("   ;:.  ").hits == []  # no tokens
    assert index.search("zzznotacorpusterm").hits == []  # nothing scores > 0


# --- tiny labeled queries (recall sanity) ---------------------------------

# (query, paper_id that should appear in the top-3). Hand-labeled against the
# committed fixtures; assertions are on top-k membership, not exact rank, so they
# are robust to minor scoring tweaks.
_LABELED = [
    ("rapamycin mTOR lifespan", "biosci-paper-004"),
    ("FOXO3 longevity variants", "biosci-paper-011"),
    ("p53 p21 DNA damage senescence", "biosci-paper-009"),
    ("senolytic meta-analysis", "biosci-paper-018"),
    ("Lamin B1 biomarker", "biosci-paper-012"),
    ("caloric restriction autophagy", "biosci-paper-014"),
]


@pytest.mark.parametrize("query,expected_id", _LABELED)
def test_labeled_queries_rank_expected_paper_in_top3(
    index: SearchIndex, query: str, expected_id: str
) -> None:
    top_ids = [h.paper_id for h in index.search(query, limit=3).hits]
    assert expected_id in top_ids, f"{expected_id} not in top-3 for {query!r}: {top_ids}"


def test_response_carries_method_params_and_provenance(index: SearchIndex) -> None:
    response = index.search("senescence", limit=2)
    assert response.method == "bm25f"
    assert response.data_source == "fixture"
    assert response.total_papers == 18
    assert "k1" in response.params and "w_title" in response.params
    payload = response.to_dict()
    assert payload["hits"][0]["term_matches"]  # explanation present in JSON shape


# --- TF-IDF cosine --------------------------------------------------------


def test_tfidf_self_similarity_is_one(index: SearchIndex) -> None:
    vectors = index.tfidf_vectors()
    for pid, vec in vectors.items():
        assert math.isclose(SearchIndex.cosine(vec, vec), 1.0, abs_tol=1e-9), pid


def test_tfidf_search_finds_topically_relevant_paper(index: SearchIndex) -> None:
    response = index.tfidf_search("rapamycin mTOR autophagy lifespan", limit=3)
    assert response.method == "tfidf-cosine"
    assert "biosci-paper-004" in [h.paper_id for h in response.hits]
    assert all(h.score > 0 for h in response.hits)


# --- topic grouping -------------------------------------------------------


def test_topics_partition_every_paper_exactly_once(index: SearchIndex) -> None:
    report = group_topics(index)
    assigned = [pid for g in report.groups for pid in g.paper_ids]
    corpus_ids = [p.paper_id for p in index.papers]
    assert sorted(assigned) == sorted(corpus_ids)
    assert len(assigned) == len(set(assigned))  # no paper in two groups


def test_topic_group_count_is_monotonic_in_threshold(index: SearchIndex) -> None:
    counts = [group_topics(index, threshold=t).num_groups
              for t in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)]
    assert counts == sorted(counts)  # raising threshold never merges groups


def test_topics_are_deterministic_and_labels_are_real_terms(index: SearchIndex) -> None:
    a = group_topics(index).to_dict()
    b = group_topics(index).to_dict()
    assert a == b
    vocab = set()
    for paper in index.papers:
        vocab.update(content_tokens(" ".join([paper.title, " ".join(paper.keywords),
                                               paper.abstract])))
    for group in group_topics(index).groups:
        assert group.label_terms  # every group is labeled
        assert set(group.label_terms) <= vocab  # labels come from actual corpus terms


def test_topic_report_carries_method_threshold_and_provenance(index: SearchIndex) -> None:
    report = group_topics(index)
    assert "single-linkage" in report.method
    assert report.threshold == DEFAULT_THRESHOLD
    assert report.data_source == "fixture"
    assert report.num_groups == sum(1 for _ in report.groups)


# --- idf helper -----------------------------------------------------------


def test_bm25_idf_is_non_negative_and_monotone() -> None:
    # Rarer terms (smaller df) weigh more; a term in every doc still weighs >= 0.
    assert bm25_idf(18, 1) > bm25_idf(18, 9) > bm25_idf(18, 18) >= 0.0


# --- CLI ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("searchcli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


def test_cli_search_text_and_json(cli_db: Path) -> None:
    res = runner.invoke(app, ["search", "cellular senescence inflammation", "--db", str(cli_db)])
    assert res.exit_code == 0, res.output
    assert "method=bm25f" in res.output
    assert "matched:" in res.output  # per-hit explanation present
    assert "biosci-paper-" in res.output

    res_json = runner.invoke(
        app, ["search", "rapamycin mTOR", "--db", str(cli_db), "--json", "--limit", "3"]
    )
    assert res_json.exit_code == 0, res_json.output
    payload = json.loads(res_json.output)
    assert payload["method"] == "bm25f"
    assert payload["hits"][0]["paper_id"] == "biosci-paper-004"
    assert payload["hits"][0]["term_matches"]  # explanation in JSON


def test_cli_search_explain_shows_per_term_breakdown(cli_db: Path) -> None:
    res = runner.invoke(app, ["search", "autophagy", "--db", str(cli_db), "--explain", "-n", "2"])
    assert res.exit_code == 0, res.output
    assert "idf=" in res.output and "wtf=" in res.output


def test_cli_search_rejects_unknown_method(cli_db: Path) -> None:
    res = runner.invoke(app, ["search", "x", "--db", str(cli_db), "--method", "bogus"])
    assert res.exit_code == 2
    assert "unknown --method" in res.output


def test_cli_topics_text_and_json(cli_db: Path) -> None:
    res = runner.invoke(app, ["topics", "--db", str(cli_db)])
    assert res.exit_code == 0, res.output
    assert "Topic report" in res.output
    assert "topic-01" in res.output

    res_json = runner.invoke(app, ["topics", "--db", str(cli_db), "--json", "--threshold", "0.15"])
    assert res_json.exit_code == 0, res_json.output
    payload = json.loads(res_json.output)
    assert payload["threshold"] == 0.15
    assert payload["total_papers"] == 18
    assigned = [pid for g in payload["groups"] for pid in g["paper_ids"]]
    assert len(assigned) == 18 and len(set(assigned)) == 18


def test_cli_search_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["search", "senescence", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
