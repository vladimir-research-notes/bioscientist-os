"""Tests for the rule-based entity and claim extraction baseline (Milestone 4).

Cover what the milestone calls for: dictionary-based biomedical entity recognition,
claim-sentence extraction from abstracts, simple relation templates, and a
confidence + full provenance on every extraction. The emphasis is on the
properties that make the baseline *auditable*: exact spans that round-trip against
the source text, transparent confidence, the four-level epistemic discipline, and
determinism. Everything runs offline from the committed fixtures or tiny in-test
papers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.evidence import (
    CURATED_TERMS,
    build_dictionary,
    extract_claims,
    extract_corpus,
    extract_entities,
    extract_paper,
)
from bioscientist_os.evidence.dictionary import EntityDictionary
from bioscientist_os.evidence.text import sentence_spans, token_spans
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import (
    BiomedicalEntity,
    Claim,
    DataSource,
    EntityType,
    EpistemicLevel,
    Paper,
)

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def dictionary() -> EntityDictionary:
    bundle = fixtures.load_all()
    return build_dictionary(bundle.proteins + bundle.associations)


@pytest.fixture(scope="module")
def papers() -> list[Paper]:
    return fixtures.load_all().papers


def _paper(pid: str, abstract: str, *, title: str = "t") -> Paper:
    return Paper(
        paper_id=pid, title=title, abstract=abstract,
        data_source=DataSource.fixture, synthetic=True,
    )


# --- span-aware text helpers ----------------------------------------------


def test_token_spans_round_trip_to_verbatim_surface() -> None:
    text = "Senescent fibroblasts secrete IL-6 and p16INK4a."
    for tok, start, end in token_spans(text):
        assert text[start:end].lower() == tok  # offsets index the original text
    assert [t for t, _, _ in token_spans("IL-6 vs IL6")] == ["il-6", "vs", "il6"]


def test_sentence_spans_reconstruct_sentences_exactly() -> None:
    text = "First claim here. Second one follows! A third?"
    spans = sentence_spans(text)
    assert [text[s:e] for s, e in spans] == [
        "First claim here.", "Second one follows!", "A third?",
    ]
    # a trailing fragment without terminal punctuation is still returned
    assert sentence_spans("no terminator") == [(0, len("no terminator"))]


# --- dictionary build -----------------------------------------------------


def test_dictionary_built_from_uniprot_with_real_xrefs(dictionary: EntityDictionary) -> None:
    il6 = dictionary.entities["ent-IL6"]
    assert il6.entity_type is EntityType.protein
    assert il6.db_xrefs["UniProt"] == "P05231"
    assert il6.db_xrefs["HGNC"] == "IL6"


def test_open_targets_adds_surface_synonym(dictionary: EntityDictionary) -> None:
    # UniProt lists the gene "IL6"; Open Targets contributes the "IL-6" surface that
    # actually appears in abstracts. Both must resolve to the same protein entity.
    assert [m.entity_id for m in dictionary.find("IL6")] == ["ent-IL6"]
    assert [m.entity_id for m in dictionary.find("IL-6")] == ["ent-IL6"]


def test_curated_terms_present_and_counts(dictionary: EntityDictionary) -> None:
    stats = dictionary.stats()
    assert stats["by_type"]["protein"] == 10  # one per UniProt record
    assert len(dictionary) == 10 + len(CURATED_TERMS)
    assert "ent-cellular-senescence" in dictionary.entities
    assert "ent-autophagy" in dictionary.entities


def test_curated_seed_is_optional() -> None:
    bundle = fixtures.load_all()
    db_only = build_dictionary(bundle.proteins + bundle.associations, include_curated=False)
    assert len(db_only) == 10  # proteins only, no process/phenotype seed


# --- entity recognition ---------------------------------------------------


def test_longest_match_recognizes_sasp_as_one_mention(dictionary: EntityDictionary) -> None:
    mentions = dictionary.find("the senescence-associated secretory phenotype is sustained")
    sasp = [m for m in mentions if m.entity_id == "ent-senescence-associated-secretory-phenotype"]
    assert len(sasp) == 1
    # the whole phrase is one span, not three single-token matches
    assert sasp[0].surface == "senescence-associated secretory phenotype"


def test_recognizer_spans_round_trip_against_abstract(
    dictionary: EntityDictionary, papers: list[Paper]
) -> None:
    by_id = {p.paper_id: p for p in papers}
    for entity in extract_corpus(papers, dictionary).all_entities:
        prov = entity.provenance
        start, end = prov.char_span
        assert by_id[prov.paper_id].abstract[start:end] == prov.source_snippet


def test_entities_carry_method_level_and_xrefs(
    dictionary: EntityDictionary, papers: list[Paper]
) -> None:
    paper = next(p for p in papers if p.paper_id == "biosci-paper-001")
    entities = extract_entities(paper, dictionary)
    assert isinstance(entities[0], BiomedicalEntity)
    il6 = next(e for e in entities if e.entity_id == "ent-IL6")
    assert il6.entity_type is EntityType.protein
    assert il6.db_xrefs["UniProt"] == "P05231"
    assert il6.confidence == 1.0
    assert il6.provenance.extraction_method == "dict:exact"
    assert il6.provenance.epistemic_level is EpistemicLevel.observed_metadata
    assert il6.provenance.data_source is DataSource.fixture
    # synonyms are the verbatim surface forms actually matched (e.g. "IL-6")
    assert "IL-6" in il6.synonyms


def test_unknown_surface_is_not_recognized(dictionary: EntityDictionary) -> None:
    # IL-8 has no UniProt fixture record, so it is honestly not recognized.
    assert dictionary.find("levels of IL-8 rose") == []


# --- claim extraction -----------------------------------------------------


def test_claims_only_from_entity_bearing_sentences(dictionary: EntityDictionary) -> None:
    paper = _paper(
        "p-mix",
        "This sentence mentions no known entity. Autophagy declined with age.",
    )
    claims = extract_claims(paper, dictionary)
    assert len(claims) == 1  # only the autophagy sentence is grounded
    assert "Autophagy declined with age." == claims[0].claim_text


def test_claim_spans_round_trip_and_carry_provenance(
    dictionary: EntityDictionary, papers: list[Paper]
) -> None:
    by_id = {p.paper_id: p for p in papers}
    for claim in extract_corpus(papers, dictionary).all_claims:
        assert isinstance(claim, Claim)
        start, end = claim.provenance.char_span
        assert by_id[claim.paper_id].abstract[start:end] == claim.claim_text
        assert claim.provenance.source_snippet == claim.claim_text
        assert claim.provenance.epistemic_level is EpistemicLevel.extracted_claim
        assert 0.0 <= claim.confidence <= 1.0
        # entity_ids are a subset of the entities recognized in that paper
        recognized = extract_entities(by_id[claim.paper_id], dictionary)
        assert set(claim.entity_ids) <= {e.entity_id for e in recognized}


def test_claim_ids_are_unique_per_paper(dictionary: EntityDictionary, papers: list[Paper]) -> None:
    for pe in extract_corpus(papers, dictionary).papers:
        ids = [c.claim_id for c in pe.claims]
        assert len(ids) == len(set(ids))
        assert all(cid.startswith(pe.paper_id + "-c") for cid in ids)


# --- relation templates ---------------------------------------------------


def test_directed_svo_triple_extracted(dictionary: EntityDictionary) -> None:
    paper = _paper("p-svo", "Senescent cells secrete IL-6 during culture.")
    claim = extract_claims(paper, dictionary)[0]
    assert claim.relation == "secretes"
    assert claim.subject == "cellular senescence"
    assert claim.object == "Interleukin-6"
    assert claim.provenance.extraction_method == "rule:svo"


def test_association_cue_triple_extracted(dictionary: EntityDictionary) -> None:
    paper = _paper("p-assoc", "FOXO3 variants were associated with longevity in carriers.")
    claim = extract_claims(paper, dictionary)[0]
    assert claim.relation == "associated_with"
    assert claim.provenance.extraction_method == "rule:assoc"


def test_corpus_captures_designed_autophagy_senescence_conflict(
    dictionary: EntityDictionary, papers: list[Paper]
) -> None:
    # Papers 006 and 007 are written to disagree on the direction of the
    # autophagy <-> senescence relationship; the SVO baseline should surface both.
    report = extract_corpus(papers, dictionary)
    rels = {
        (c.paper_id, c.relation)
        for c in report.all_claims
        if c.subject == "autophagy" and c.object == "cellular senescence"
    }
    assert ("biosci-paper-006", "promotes") in rels
    assert ("biosci-paper-007", "restrains") in rels


# --- confidence -----------------------------------------------------------


def test_confidence_is_additive_and_transparent(dictionary: EntityDictionary) -> None:
    # one entity, no triple, no reporting cue -> base 0.35
    single = extract_claims(_paper("p1", "FOXO3 was characterized here."), dictionary)[0]
    assert single.confidence == pytest.approx(0.35)
    # two entities (+0.25) and a reporting cue "observed" (+0.10), no triple -> 0.70
    multi = extract_claims(_paper("p2", "FOXO3 and SIRT1 were observed together."), dictionary)[0]
    assert multi.confidence == pytest.approx(0.70)


# --- determinism + report shape -------------------------------------------


def test_extraction_is_deterministic(dictionary: EntityDictionary, papers: list[Paper]) -> None:
    first = extract_corpus(papers, dictionary).to_dict()
    second = extract_corpus(papers, dictionary).to_dict()
    assert first == second


def test_report_csv_rows_match_columns(dictionary: EntityDictionary, papers: list[Paper]) -> None:
    from bioscientist_os.evidence.model import ExtractionReport

    report = extract_corpus(papers, dictionary)
    assert report.num_entities > 0 and report.num_claims > 0 and report.num_relations > 0
    for row in report.claim_rows():
        assert set(row) == set(ExtractionReport.CLAIM_COLUMNS)
    for row in report.entity_rows():
        assert set(row) == set(ExtractionReport.ENTITY_COLUMNS)


def test_extract_paper_matches_separate_calls(
    dictionary: EntityDictionary, papers: list[Paper]
) -> None:
    paper = papers[0]
    pe = extract_paper(paper, dictionary)
    assert [e.entity_id for e in pe.entities] == [
        e.entity_id for e in extract_entities(paper, dictionary)
    ]
    assert [c.claim_id for c in pe.claims] == [
        c.claim_id for c in extract_claims(paper, dictionary)
    ]


# --- CLI ------------------------------------------------------------------


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("extractcli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


def test_cli_extract_text_and_json(cli_db: Path) -> None:
    res = runner.invoke(app, ["extract", "--db", str(cli_db)])
    assert res.exit_code == 0, res.output
    assert "Extraction" in res.output
    assert "dict:exact" in res.output
    assert "biosci-paper-001" in res.output

    res_json = runner.invoke(app, ["extract", "--db", str(cli_db), "--json"])
    assert res_json.exit_code == 0, res_json.output
    payload = json.loads(res_json.output)
    assert payload["total_papers"] == 18
    assert payload["num_claims"] > 0 and payload["num_relations"] > 0
    assert payload["papers"][0]["paper_id"] == "biosci-paper-001"


def test_cli_extract_paper_filter_and_min_confidence(cli_db: Path) -> None:
    res = runner.invoke(app, ["extract", "--db", str(cli_db), "--paper", "biosci-paper-006"])
    assert res.exit_code == 0, res.output
    assert "biosci-paper-006" in res.output
    assert "biosci-paper-001" not in res.output

    res_hi = runner.invoke(
        app,
        ["extract", "--db", str(cli_db), "--paper", "biosci-paper-006",
         "--min-confidence", "0.99"],
    )
    assert res_hi.exit_code == 0, res_hi.output
    assert "confidence >= 0.99" in res_hi.output


def test_cli_extract_unknown_paper_errors(cli_db: Path) -> None:
    res = runner.invoke(app, ["extract", "--db", str(cli_db), "--paper", "nope"])
    assert res.exit_code == 1
    assert "no paper with paper_id" in res.output


def test_cli_extract_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["extract", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
