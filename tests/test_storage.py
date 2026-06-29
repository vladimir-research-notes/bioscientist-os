"""Unit tests for the SQLite storage backend (Milestone 2).

Exercise the store in isolation from the fixture corpus: idempotent upserts,
exact round-trip back into the typed schemas, content-determinism of the digest,
and the aggregate views used by ``biosci stats``.
"""

from __future__ import annotations

from pathlib import Path

from bioscientist_os.schemas import (
    Author,
    DatabaseRecord,
    Paper,
    ResearchQuestion,
)
from bioscientist_os.storage import SCHEMA_VERSION, SQLiteStore


def _paper(pid: str = "p1") -> Paper:
    return Paper(
        paper_id=pid,
        title="A senescence paper",
        authors=[Author(name="A. Mercer", orcid="0000-0000-0000-0001"), Author(name="R. Halloran")],
        journal="Journal of Cell Senescence",
        year=2008,
        abstract="Senescent fibroblasts secrete IL-6.",
        keywords=["senescence", "IL-6"],
        url="https://example.org/p1",
        external_ids={"DOI": "10.0000/biosci-os.fixture.0001"},
        synthetic=True,
    )


def _record(rid: str = "P05231") -> DatabaseRecord:
    return DatabaseRecord(
        record_id=rid,
        source="UniProt",
        record_type="protein",
        fields={"gene": "IL6", "accession": rid, "xrefs": {"HGNC_symbol": "IL6"}},
        synthetic=False,
    )


def _question(qid: str = "rq1") -> ResearchQuestion:
    return ResearchQuestion(
        question_id=qid,
        text="What links senescence to inflammation?",
        entities_of_interest=["IL6", "senescence"],
    )


def test_initialize_creates_tables_and_meta(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    with SQLiteStore(db) as store:
        assert not store.is_initialized()
        store.initialize()
        assert store.is_initialized()
        meta = store.meta()
        assert meta["schema_version"] == str(SCHEMA_VERSION)
        assert "bioscientist_os_version" in meta
    assert db.is_file()


def test_upsert_reports_insert_then_update(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path / "x.db") as store:
        store.initialize()
        assert store.upsert_paper(_paper()) is True  # newly inserted
        assert store.upsert_paper(_paper()) is False  # updated in place
        store.commit()
        assert store.table_counts()["papers"] == 1  # no duplicate row


def test_paper_round_trip_is_exact(tmp_path: Path) -> None:
    paper = _paper()
    with SQLiteStore(tmp_path / "x.db") as store:
        store.initialize()
        store.upsert_paper(paper)
        store.commit()
        (back,) = list(store.iter_papers())
    assert back == paper


def test_database_record_and_question_round_trip(tmp_path: Path) -> None:
    record, question = _record(), _question()
    with SQLiteStore(tmp_path / "x.db") as store:
        store.initialize()
        store.upsert_database_record(record)
        store.upsert_research_question(question)
        store.commit()
        assert list(store.iter_database_records()) == [record]
        assert list(store.iter_research_questions()) == [question]


def test_breakdown_groups_by_source_and_type(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path / "x.db") as store:
        store.initialize()
        store.upsert_database_record(_record("P1"))
        store.upsert_database_record(_record("P2"))
        store.upsert_database_record(
            DatabaseRecord(
                record_id="OT1", source="OpenTargets", record_type="association",
                fields={"target_gene": "IL6"}, synthetic=True,
            )
        )
        store.commit()
        assert store.record_breakdown() == [
            ("OpenTargets", "association", 1),
            ("UniProt", "protein", 2),
        ]
        assert store.table_counts()["database_records"] == 3


def test_content_digest_is_insertion_order_independent(tmp_path: Path) -> None:
    p1, p2 = _paper("p1"), _paper("p2")
    with SQLiteStore(tmp_path / "a.db") as a:
        a.initialize()
        a.upsert_paper(p1)
        a.upsert_paper(p2)
        a.commit()
        digest_a = a.content_digest()
    with SQLiteStore(tmp_path / "b.db") as b:
        b.initialize()
        b.upsert_paper(p2)  # reversed insertion order
        b.upsert_paper(p1)
        b.commit()
        digest_b = b.content_digest()
    assert digest_a == digest_b


def test_content_digest_changes_with_content(tmp_path: Path) -> None:
    with SQLiteStore(tmp_path / "a.db") as a:
        a.initialize()
        a.upsert_paper(_paper())
        a.commit()
        before = a.content_digest()
    with SQLiteStore(tmp_path / "b.db") as b:
        b.initialize()
        edited = _paper()
        edited = edited.model_copy(update={"title": "A different title"})
        b.upsert_paper(edited)
        b.commit()
        after = b.content_digest()
    assert before != after


def test_meta_is_excluded_from_digest(tmp_path: Path) -> None:
    # Two stores with identical data but a divergent extra meta key still agree on
    # the content digest, because the digest covers data tables only.
    with SQLiteStore(tmp_path / "a.db") as a:
        a.initialize()
        a.upsert_paper(_paper())
        a.commit()
        digest_a = a.content_digest()
    with SQLiteStore(tmp_path / "b.db") as b:
        b.initialize()
        b._set_meta("some_extra_key", "value")
        b.upsert_paper(_paper())
        b.commit()
        digest_b = b.content_digest()
    assert digest_a == digest_b
