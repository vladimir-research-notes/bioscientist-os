"""Tests for the evidence-table builder (Milestone 5).

Cover what the milestone calls for: evidence tables grouped by a research question,
with the columns ``docs/PLAN.md`` specifies and — the project's central discipline —
full provenance on every cell plus a *clearly labeled* support/conflict/unknown
signal that is never presented as a biological verdict. The emphasis is on the
properties that make the table auditable: exact snippet spans that round-trip
against the source abstract, 100% provenance coverage, a transparent support
heuristic, the four-level epistemic separation, and determinism. Everything runs
offline from the committed fixtures or tiny in-test papers.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.evidence import (
    EvidenceReport,
    build_dictionary,
    build_evidence_report,
    classify_support,
    extract_corpus,
    resolve_question,
    resolve_question_entities,
)
from bioscientist_os.evidence.dictionary import EntityDictionary
from bioscientist_os.evidence.model import ExtractionReport
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import (
    EpistemicLevel,
    EvidenceItem,
    EvidenceTable,
    Paper,
    ResearchQuestion,
    SupportLabel,
)

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> fixtures.FixtureBundle:
    return fixtures.load_all()


@pytest.fixture(scope="module")
def dictionary(bundle: fixtures.FixtureBundle) -> EntityDictionary:
    return build_dictionary(bundle.proteins + bundle.associations)


@pytest.fixture(scope="module")
def extraction(bundle: fixtures.FixtureBundle, dictionary: EntityDictionary) -> ExtractionReport:
    return extract_corpus(bundle.papers, dictionary)


@pytest.fixture(scope="module")
def papers_by_id(bundle: fixtures.FixtureBundle) -> dict[str, Paper]:
    return {p.paper_id: p for p in bundle.papers}


def _question(qid: str, text: str, entities: list[str]) -> ResearchQuestion:
    return ResearchQuestion(question_id=qid, text=text, entities_of_interest=entities)


def _build(
    bundle: fixtures.FixtureBundle,
    dictionary: EntityDictionary,
    extraction: ExtractionReport,
    question: ResearchQuestion,
    **kw,
) -> EvidenceReport:
    return build_evidence_report(
        question, extraction, dictionary, bundle.proteins + bundle.associations, **kw
    )


# --- support classifier (transparent textual heuristic) -------------------


def test_classify_support_affirms_relationship() -> None:
    label, reason = classify_support(
        "Senescent cells secrete IL-6 during culture.", has_relation=True
    )
    assert label is SupportLabel.support
    assert "relation triple" in reason


def test_classify_support_negation_is_conflict_and_wins() -> None:
    # A strong negation cue overrides any co-occurring relationship verb.
    label, reason = classify_support(
        "FOXO3 variants were not associated with longevity.", has_relation=False
    )
    assert label is SupportLabel.conflict
    assert "not associated" in reason

    label2, _ = classify_support("p16INK4a did not increase with passage.", has_relation=True)
    assert label2 is SupportLabel.conflict  # negation beats the (spurious) triple


def test_classify_support_unknown_is_the_default() -> None:
    label, reason = classify_support(
        "p16INK4a is widely used as a marker of cellular senescence.", has_relation=False
    )
    assert label is SupportLabel.unknown
    assert reason == "no affirming or negating cue"


def test_classify_support_triple_survives_weak_contrast() -> None:
    # "without" is a weak contrast cue; an asserted relation triple still reads as support.
    label, reason = classify_support(
        "SIRT1 reduced secretion of IL-6 without affecting proliferation.", has_relation=True
    )
    assert label is SupportLabel.support
    assert "without" in reason  # the hedge is recorded, not hidden

    # ... but a bare contrast with no relationship reads as conflict.
    label2, _ = classify_support("However, levels remained stable.", has_relation=False)
    assert label2 is SupportLabel.conflict


# --- question entity resolution -------------------------------------------


def test_resolve_question_entities_matches_fixture_entities(dictionary: EntityDictionary) -> None:
    q = _question(
        "rq-senescence-inflammation",
        "What evidence links cellular senescence to chronic inflammation?",
        ["IL6", "CDKN2A", "SASP", "senescence", "inflammation"],
    )
    ids, unmatched = resolve_question_entities(q, dictionary)
    assert "ent-IL6" in ids
    assert "ent-CDKN2A" in ids
    assert "ent-senescence-associated-secretory-phenotype" in ids
    assert "ent-cellular-senescence" in ids
    assert "ent-inflammation" in ids
    assert unmatched == []  # every fixture entity of interest is recognized


def test_resolve_question_entities_reports_unmatched_terms(dictionary: EntityDictionary) -> None:
    q = _question("rq-x", "A question about senescence.", ["senescence", "IL-8", "telomerase"])
    ids, unmatched = resolve_question_entities(q, dictionary)
    assert "ent-cellular-senescence" in ids
    # IL-8 and telomerase have no fixture record, so they are honestly unmatched.
    assert set(unmatched) == {"IL-8", "telomerase"}


# --- evidence table assembly ----------------------------------------------


def test_rows_only_from_claims_mentioning_a_question_entity(
    bundle, dictionary, extraction
) -> None:
    q = _question("rq-foxo3", "FOXO3 and longevity", ["FOXO3"])
    report = _build(bundle, dictionary, extraction, q)
    assert report.num_rows > 0
    foxo3_claims = {
        c.claim_id for c in extraction.all_claims if "ent-FOXO3" in c.entity_ids
    }
    assert {r.claim_id for r in report.rows} <= foxo3_claims
    # every row genuinely contains the entity name
    assert all("Forkhead box protein O3" in r.entity_names for r in report.rows)


def test_every_row_has_full_provenance_at_claim_level(
    bundle, dictionary, extraction, papers_by_id
) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    report = _build(bundle, dictionary, extraction, q)
    assert report.num_rows > 0
    assert report.provenance_coverage == 1.0
    for r in report.rows:
        assert isinstance(r, EvidenceItem)
        prov = r.provenance
        assert prov.paper_id == r.paper_id
        assert prov.source_snippet == r.claim_text
        # the snippet's span reproduces the exact abstract text it was read from
        start, end = prov.char_span
        assert papers_by_id[r.paper_id].abstract[start:end] == r.claim_text
        # the cell is anchored to the extracted claim; other facets live elsewhere
        assert prov.epistemic_level is EpistemicLevel.extracted_claim
        assert 0.0 <= r.confidence <= 1.0
        assert r.notes and r.notes.startswith("rule:support-cues ->")


def test_support_counts_sum_to_rows_and_cover_all_labels(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    report = _build(bundle, dictionary, extraction, q)
    counts = report.support_counts()
    assert set(counts) == {label.value for label in SupportLabel}
    assert sum(counts.values()) == report.num_rows
    # the senescence corpus exercises all three labels
    assert counts["support"] > 0 and counts["conflict"] > 0 and counts["unknown"] > 0


def test_database_links_combine_xrefs_and_associations(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    report = _build(bundle, dictionary, extraction, q)
    # a row mentioning IL-6 should link its UniProt/HGNC xrefs and the Open Targets assoc
    il6_rows = [r for r in report.rows if "Interleukin-6" in r.entity_names]
    assert il6_rows
    links = set().union(*(set(r.database_links) for r in il6_rows))
    assert "UniProt:P05231" in links
    assert "HGNC:IL6" in links
    assert "OpenTargets:OTAF-0002" in links
    # the association descriptor is spelled out in notes (inferred relation, labeled)
    assert any("OTAF-0002" in r.notes and "inflammaging" in r.notes for r in il6_rows)


def test_per_row_label_is_textual_not_cross_paper_verdict(bundle, dictionary, extraction) -> None:
    # Papers 006 and 007 disagree on the *direction* of autophagy<->senescence, yet each
    # sentence asserts a relationship, so both rows are labeled support. The per-row label
    # is about phrasing, not whether papers agree (a documented limitation).
    q = next(q for q in bundle.questions if q.question_id == "rq-autophagy-senescence")
    report = _build(bundle, dictionary, extraction, q)
    by_paper: dict[str, list[EvidenceItem]] = {}
    for r in report.rows:
        by_paper.setdefault(r.paper_id, []).append(r)

    def has_support(pid: str) -> bool:
        return any(r.support_conflict_unknown is SupportLabel.support for r in by_paper[pid])

    assert has_support("biosci-paper-006")
    assert has_support("biosci-paper-007")


def test_rows_sorted_by_confidence_then_ids(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-longevity-pathways")
    report = _build(bundle, dictionary, extraction, q)
    keys = [(-r.confidence, r.paper_id, r.claim_id) for r in report.rows]
    assert keys == sorted(keys)


def test_min_confidence_and_limit(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    full = _build(bundle, dictionary, extraction, q)
    filtered = _build(bundle, dictionary, extraction, q, min_confidence=0.7)
    assert filtered.num_rows < full.num_rows
    assert all(r.confidence >= 0.7 for r in filtered.rows)
    limited = _build(bundle, dictionary, extraction, q, limit=3)
    assert limited.num_rows == 3
    assert [r.claim_id for r in limited.rows] == [r.claim_id for r in full.rows[:3]]


def test_table_is_typed_evidence_table_with_ids(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-autophagy-senescence")
    report = _build(bundle, dictionary, extraction, q)
    assert isinstance(report.table, EvidenceTable)
    assert report.table.table_id == "evtbl-rq-autophagy-senescence"
    assert report.table.research_question_id == "rq-autophagy-senescence"
    assert "evidence-table-builder" in report.table.generated_by


def test_build_is_deterministic(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    first = _build(bundle, dictionary, extraction, q).to_dict()
    second = _build(bundle, dictionary, extraction, q).to_dict()
    assert first == second


def test_csv_rows_match_declared_columns(bundle, dictionary, extraction) -> None:
    q = next(q for q in bundle.questions if q.question_id == "rq-senescence-inflammation")
    report = _build(bundle, dictionary, extraction, q)
    assert report.num_rows > 0
    plan_columns = {
        "claim_id", "claim_text", "entity_names", "paper_id", "source_snippet",
        "support_conflict_unknown", "extraction_method", "confidence",
        "database_links", "notes",
    }
    assert plan_columns <= set(EvidenceReport.EVIDENCE_COLUMNS)  # PLAN's columns present
    for row in report.evidence_rows():
        assert set(row) == set(EvidenceReport.EVIDENCE_COLUMNS)


# --- question resolution (CLI mapping) ------------------------------------


def test_resolve_question_by_text_uses_stored_question(bundle, dictionary) -> None:
    text = "What evidence links cellular senescence to chronic inflammation?"
    q = resolve_question(bundle.questions, dictionary, question_text=text)
    assert q.question_id == "rq-senescence-inflammation"
    assert q.entities_of_interest  # curated entities are picked up


def test_resolve_question_by_id(bundle, dictionary) -> None:
    q = resolve_question(bundle.questions, dictionary, question_id="rq-autophagy-senescence")
    assert q.question_id == "rq-autophagy-senescence"
    with pytest.raises(KeyError):
        resolve_question(bundle.questions, dictionary, question_id="nope")


def test_resolve_question_synthesizes_for_adhoc_text(bundle, dictionary) -> None:
    q = resolve_question(bundle.questions, dictionary, question_text="What about rapamycin?")
    assert q.question_id.startswith("rq-adhoc-")
    assert q.entities_of_interest == []  # synthesized: entities resolved from text alone


# --- CLI ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("evidencecli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


def test_cli_evidence_text_output(cli_db: Path) -> None:
    res = runner.invoke(
        app,
        ["evidence", "--db", str(cli_db),
         "--question", "What evidence links cellular senescence to chronic inflammation?"],
    )
    assert res.exit_code == 0, res.output
    assert "Evidence table" in res.output
    assert "rq-senescence-inflammation" in res.output
    assert "provenance coverage: 100%" in res.output
    assert "heuristic textual signal" in res.output  # safety framing present


def test_cli_evidence_json_and_csv_out(cli_db: Path, tmp_path: Path) -> None:
    out_csv = tmp_path / "sub" / "evidence_table.csv"
    res = runner.invoke(
        app,
        ["evidence", "--db", str(cli_db), "--question-id", "rq-autophagy-senescence",
         "--out", str(out_csv), "--json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["research_question_id"] == "rq-autophagy-senescence"
    assert payload["provenance_coverage"] == 1.0
    assert payload["num_rows"] == len(payload["rows"])

    # the CSV was written (parent dirs created) with the declared header + one row each
    assert out_csv.is_file()
    with out_csv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == payload["num_rows"]
    assert set(rows[0]) == set(EvidenceReport.EVIDENCE_COLUMNS)


def test_cli_evidence_requires_a_question(cli_db: Path) -> None:
    res = runner.invoke(app, ["evidence", "--db", str(cli_db)])
    assert res.exit_code == 2
    assert "--question" in res.output


def test_cli_evidence_unknown_question_id_errors(cli_db: Path) -> None:
    res = runner.invoke(app, ["evidence", "--db", str(cli_db), "--question-id", "nope"])
    assert res.exit_code == 1
    assert "no stored research question" in res.output


def test_cli_evidence_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["evidence", "--db", str(empty), "--question", "anything"])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
