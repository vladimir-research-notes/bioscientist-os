"""Tests for the typed data schemas (Milestone 1).

These cover three things the project relies on: schemas validate on construction,
they round-trip losslessly through JSON, and the provenance/epistemic discipline
is actually enforced by the type system rather than left to convention.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import bioscientist_os
from bioscientist_os.schemas import (
    Author,
    BiomedicalEntity,
    Claim,
    DatabaseRecord,
    DataSource,
    EntityType,
    EpistemicLevel,
    EvidenceItem,
    EvidenceTable,
    Paper,
    Provenance,
    ResearchQuestion,
    SupportLabel,
    WorkbenchRun,
)


def _claim_provenance() -> Provenance:
    return Provenance(
        paper_id="biosci-paper-001",
        source_snippet="senescent cells secrete IL-6",
        char_span=(0, 28),
        extraction_method="rule:svo",
        epistemic_level=EpistemicLevel.extracted_claim,
    )


def _sample_objects() -> list:
    prov = _claim_provenance()
    return [
        Author(name="A. Mercer", orcid="0000-0002-1825-0097"),
        Paper(
            paper_id="biosci-paper-001",
            title="Senescent fibroblasts secrete IL-6",
            authors=[Author(name="A. Mercer")],
            journal="Journal of Cell Senescence",
            year=2008,
            abstract="Senescent cells secrete IL-6.",
            keywords=["senescence", "IL-6"],
            external_ids={"DOI": "10.0000/biosci-os.fixture.0001"},
            synthetic=True,
        ),
        DatabaseRecord(
            record_id="P05231",
            source="UniProt",
            record_type="protein",
            fields={"gene": "IL6"},
            synthetic=False,
        ),
        BiomedicalEntity(
            entity_id="ent-IL6",
            name="Interleukin-6",
            entity_type=EntityType.protein,
            synonyms=["IL-6"],
            db_xrefs={"UniProt": "P05231"},
            provenance=Provenance(
                paper_id="biosci-paper-001",
                source_snippet="IL-6",
                extraction_method="dict:entity",
                epistemic_level=EpistemicLevel.observed_metadata,
            ),
        ),
        Claim(
            claim_id="claim-001",
            claim_text="senescent cells secrete IL-6",
            paper_id="biosci-paper-001",
            subject="senescent cells",
            relation="secrete",
            object="IL-6",
            entity_ids=["ent-IL6"],
            confidence=0.7,
            provenance=prov,
        ),
        EvidenceItem(
            claim_id="claim-001",
            claim_text="senescent cells secrete IL-6",
            entity_names=["Interleukin-6"],
            paper_id="biosci-paper-001",
            support_conflict_unknown=SupportLabel.support,
            database_links=["UniProt:P05231"],
            confidence=0.7,
            provenance=prov,
        ),
        ResearchQuestion(
            question_id="rq-1",
            text="What links senescence to inflammation?",
            entities_of_interest=["IL6"],
        ),
        EvidenceTable(
            table_id="tbl-1",
            research_question_id="rq-1",
            research_question_text="What links senescence to inflammation?",
            rows=[
                EvidenceItem(
                    claim_id="claim-001",
                    claim_text="senescent cells secrete IL-6",
                    paper_id="biosci-paper-001",
                    confidence=0.7,
                    provenance=prov,
                )
            ],
            generated_by="run-1",
        ),
        WorkbenchRun(
            run_id="run-1",
            inputs={"question": "rq-1"},
            versions={"bioscientist_os": "0.0.0"},
            started_at="2026-06-29T00:00:00Z",
        ),
    ]


@pytest.mark.parametrize("obj", _sample_objects(), ids=lambda o: type(o).__name__)
def test_schema_json_round_trip(obj) -> None:
    """Every schema serializes to JSON and parses back to an equal object."""
    restored = type(obj).model_validate_json(obj.model_dump_json())
    assert restored == obj


def test_epistemic_levels_match_package_constant() -> None:
    """The enum and the package-level EPISTEMIC_LEVELS agree on names and order."""
    package_names = [name for name, _ in bioscientist_os.EPISTEMIC_LEVELS]
    assert [lvl.display for lvl in EpistemicLevel] == package_names


def test_data_source_values() -> None:
    assert {ds.value for ds in DataSource} == {"fixture", "cache", "live"}
    paper = Paper(paper_id="p", title="t", abstract="", synthetic=True)
    assert paper.data_source is DataSource.fixture


def test_provenance_is_required_on_derived_objects() -> None:
    """A Claim cannot be built without provenance — the discipline is enforced."""
    with pytest.raises(ValidationError):
        Claim(claim_id="c", claim_text="x", paper_id="p", confidence=0.5)


def test_extraction_method_must_be_nonempty() -> None:
    with pytest.raises(ValidationError):
        Provenance(extraction_method="", epistemic_level=EpistemicLevel.extracted_claim)


def test_confidence_bounds_enforced() -> None:
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            Claim(
                claim_id="c",
                claim_text="x",
                paper_id="p",
                confidence=bad,
                provenance=_claim_provenance(),
            )


def test_char_span_validation() -> None:
    base = dict(extraction_method="rule:svo", epistemic_level=EpistemicLevel.extracted_claim)
    # start > end is rejected.
    with pytest.raises(ValidationError):
        Provenance(char_span=(10, 2), **base)
    # negative offsets are rejected.
    with pytest.raises(ValidationError):
        Provenance(char_span=(-1, 5), **base)
    # a valid span survives a round-trip as a tuple.
    prov = Provenance(char_span=(3, 9), **base)
    assert prov.char_span == (3, 9)
    restored = Provenance.model_validate_json(prov.model_dump_json())
    assert restored.char_span == (3, 9)


def test_claim_provenance_paper_must_match() -> None:
    bad_prov = Provenance(
        paper_id="biosci-paper-999",
        extraction_method="rule:svo",
        epistemic_level=EpistemicLevel.extracted_claim,
    )
    with pytest.raises(ValidationError):
        Claim(
            claim_id="c",
            claim_text="x",
            paper_id="biosci-paper-001",
            confidence=0.5,
            provenance=bad_prov,
        )


def test_extra_fields_are_forbidden() -> None:
    """Unexpected keys fail loudly, so a malformed fixture cannot slip through."""
    with pytest.raises(ValidationError):
        Paper(paper_id="p", title="t", abstract="", synthetic=True, bogus=1)


def test_support_label_defaults_to_unknown() -> None:
    item = EvidenceItem(
        claim_id="c",
        claim_text="x",
        paper_id="p",
        confidence=0.5,
        provenance=_claim_provenance(),
    )
    assert item.support_conflict_unknown is SupportLabel.unknown


def test_evidence_table_provenance_coverage() -> None:
    full = _claim_provenance()  # has paper_id + source_snippet
    thin = Provenance(extraction_method="rule:svo", epistemic_level=EpistemicLevel.extracted_claim)

    def item(prov: Provenance) -> EvidenceItem:
        return EvidenceItem(
            claim_id="c",
            claim_text="x",
            paper_id="biosci-paper-001",
            confidence=0.5,
            provenance=prov,
        )

    empty = EvidenceTable(
        table_id="t", research_question_id="q", research_question_text="q?", generated_by="run"
    )
    assert empty.provenance_coverage == 1.0  # vacuously complete

    mixed = EvidenceTable(
        table_id="t",
        research_question_id="q",
        research_question_text="q?",
        rows=[item(full), item(thin)],
        generated_by="run",
    )
    assert mixed.provenance_coverage == 0.5
