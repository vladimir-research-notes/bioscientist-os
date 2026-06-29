"""Tests for fixture ingestion into local storage (Milestone 2).

Cover the four properties the milestone calls for: schema validation on ingest,
ingestion count checks, idempotent (duplicate-safe) re-ingest, and
reproducible/deterministic database creation. Also smoke-tests the ``biosci
ingest`` / ``biosci stats`` CLI commands. Everything runs offline from the
committed fixtures or tiny in-test corpora.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.storage import SQLiteStore

runner = CliRunner()


# --- helpers --------------------------------------------------------------


def _write_corpus(
    root: Path,
    *,
    papers: list[dict] | None = None,
    proteins: list[dict] | None = None,
    associations: list[dict] | None = None,
    questions: list[dict] | None = None,
) -> Path:
    """Write a minimal but structurally complete fixtures tree under ``root``."""
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "uniprot").mkdir(parents=True, exist_ok=True)
    (root / "opentargets").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "papers.json").write_text(json.dumps(papers or []), encoding="utf-8")
    (root / "uniprot" / "proteins.json").write_text(json.dumps(proteins or []), encoding="utf-8")
    (root / "opentargets" / "associations.json").write_text(
        json.dumps(associations or []), encoding="utf-8"
    )
    (root / "questions.json").write_text(json.dumps(questions or []), encoding="utf-8")
    return root


_MINIMAL = dict(
    papers=[{"paper_id": "p1", "title": "t", "abstract": "a", "synthetic": True}],
    proteins=[{"record_id": "P1", "source": "UniProt", "record_type": "protein",
               "fields": {"gene": "IL6"}, "synthetic": False}],
    associations=[{"record_id": "OT1", "source": "OpenTargets", "record_type": "association",
                   "fields": {"target_gene": "IL6"}, "synthetic": True}],
    questions=[{"question_id": "q1", "text": "why?"}],
)


# --- count checks ---------------------------------------------------------


def test_ingest_committed_fixtures_counts(tmp_path: Path) -> None:
    report = ingest_fixtures(db_path=tmp_path / "db.sqlite")
    assert (report.papers, report.proteins, report.associations, report.questions) == (18, 10, 9, 3)
    assert report.total_records == 40
    assert report.inserted == 40 and report.updated == 0
    with SQLiteStore(report.db_path) as store:
        counts = store.table_counts()
    assert counts == {"papers": 18, "database_records": 19, "research_questions": 3}


def test_ingest_round_trips_against_loader(tmp_path: Path) -> None:
    """Records read back from the database equal the records the loader produced."""
    bundle = fixtures.load_all()
    report = ingest_fixtures(db_path=tmp_path / "db.sqlite")
    with SQLiteStore(report.db_path) as store:
        papers = list(store.iter_papers())
        records = list(store.iter_database_records())
        questions = list(store.iter_research_questions())
    assert papers == sorted(bundle.papers, key=lambda p: p.paper_id)
    expected_records = sorted(
        (*bundle.proteins, *bundle.associations), key=lambda r: (r.source, r.record_id)
    )
    assert records == expected_records
    assert questions == sorted(bundle.questions, key=lambda q: q.question_id)


# --- idempotent / duplicate handling --------------------------------------


def test_reingest_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    first = ingest_fixtures(db_path=db)
    second = ingest_fixtures(db_path=db)
    # No new rows on the second pass; everything is an in-place update.
    assert second.inserted == 0
    assert second.updated == first.total_records
    # Counts and content are unchanged -> no duplicates.
    assert (second.papers, second.proteins, second.associations, second.questions) == (
        first.papers, first.proteins, first.associations, first.questions
    )
    assert second.digest == first.digest


def test_reset_rebuilds_cleanly(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    ingest_fixtures(db_path=db)
    report = ingest_fixtures(db_path=db, reset=True)
    # A reset deletes the file first, so every row is freshly inserted again.
    assert report.inserted == report.total_records
    assert report.updated == 0


# --- determinism ----------------------------------------------------------


def test_database_creation_is_deterministic(tmp_path: Path) -> None:
    a = ingest_fixtures(db_path=tmp_path / "a.sqlite")
    b = ingest_fixtures(db_path=tmp_path / "b.sqlite")
    assert a.digest == b.digest


# --- schema validation on ingest ------------------------------------------


def test_malformed_fixture_aborts_before_writing_db(tmp_path: Path) -> None:
    src = _write_corpus(
        tmp_path / "fx",
        papers=[{"paper_id": "p1", "title": "ok", "abstract": "", "synthetic": True},
                {"paper_id": "p2", "title": "bad", "abstract": ""}],  # missing `synthetic`
    )
    db = tmp_path / "out" / "db.sqlite"
    with pytest.raises(fixtures.FixtureError, match=r"papers\.json\[1\]"):
        ingest_fixtures(src, db_path=db)
    # Validation happens before any file is created: no partial database, and the
    # parent directory was not even made.
    assert not db.exists()
    assert not db.parent.exists()


def test_custom_minimal_corpus_ingests(tmp_path: Path) -> None:
    src = _write_corpus(tmp_path / "fx", **_MINIMAL)
    report = ingest_fixtures(src, db_path=tmp_path / "db.sqlite")
    assert (report.papers, report.proteins, report.associations, report.questions) == (1, 1, 1, 1)


# --- CLI ------------------------------------------------------------------


def test_cli_ingest_then_stats(tmp_path: Path) -> None:
    db = tmp_path / "cli.db"
    src = _write_corpus(tmp_path / "fx", **_MINIMAL)

    res_ingest = runner.invoke(app, ["ingest", str(src), "--db", str(db)])
    assert res_ingest.exit_code == 0, res_ingest.output
    assert "Ingested 4 records" in res_ingest.output
    assert "observed metadata" in res_ingest.output  # epistemic level surfaced
    assert db.is_file()

    res_stats = runner.invoke(app, ["stats", "--db", str(db), "--json"])
    assert res_stats.exit_code == 0, res_stats.output
    payload = json.loads(res_stats.output)
    assert payload["counts"] == {"papers": 1, "database_records": 2, "research_questions": 1}
    assert payload["content_digest"]


def test_cli_stats_on_uninitialized_db_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()  # a file that exists but is not our database
    res = runner.invoke(app, ["stats", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
