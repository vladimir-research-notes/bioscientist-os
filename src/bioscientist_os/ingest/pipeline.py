"""Ingest the committed fixtures into a local SQLite database (Milestone 2).

This is the orchestration layer that sits between the parse-only fixture loader
(:mod:`bioscientist_os.fixtures`, Milestone 1) and the storage backend
(:class:`bioscientist_os.storage.SQLiteStore`):

1. **load + validate** every fixture record into its typed pydantic schema
   (a malformed corpus raises :class:`bioscientist_os.fixtures.FixtureError`
   *before* any database file is touched, so a failed ingest leaves no partial
   database);
2. **upsert** each record into the database, keyed by its stable id, so
   re-ingesting the same fixtures is idempotent (no duplicate rows);
3. **report** exactly what was written, with a content digest for reproducibility.

Everything here is offline and CPU-only. Papers and database records are *observed
metadata* (``data_source = fixture``); no claims, relations, or hypotheses are
produced at ingestion time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bioscientist_os import fixtures
from bioscientist_os.storage import SQLiteStore


@dataclass(frozen=True)
class IngestReport:
    """What one :func:`ingest_fixtures` call wrote, for CLI display and tests.

    ``papers`` / ``proteins`` / ``associations`` / ``questions`` are the number of
    each kind of record present in the database after the call (which, because
    writes are idempotent upserts, equals the fixture count on every run).
    ``inserted`` / ``updated`` break down the writes performed *this* call: a first
    ingest into a fresh database is all inserts; an identical re-ingest is all
    updates with no new rows. ``digest`` is the storage content digest.
    """

    db_path: Path
    papers: int
    proteins: int
    associations: int
    questions: int
    inserted: int
    updated: int
    digest: str

    @property
    def total_records(self) -> int:
        return self.papers + self.proteins + self.associations + self.questions


def ingest_fixtures(
    fixtures_dir: str | Path | None = None,
    *,
    db_path: str | Path,
    reset: bool = False,
) -> IngestReport:
    """Load the fixtures under ``fixtures_dir`` and write them to ``db_path``.

    Parameters
    ----------
    fixtures_dir:
        Fixture root (defaults to the committed ``data/fixtures/``).
    db_path:
        SQLite file to create or update. Parent directories are created.
    reset:
        If ``True``, delete an existing database first so the build starts clean.
        Omit it for the normal idempotent path (re-ingest updates in place).
    """
    # Load + validate first. If a fixture is malformed this raises before we create
    # or modify any database file, so a failed ingest never leaves a partial DB.
    bundle = fixtures.load_all(fixtures_dir)

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset and db_path.exists():
        db_path.unlink()

    inserted = 0
    updated = 0
    with SQLiteStore(db_path) as store:
        store.initialize()
        for paper in bundle.papers:
            inserted += store.upsert_paper(paper)
        for record in (*bundle.proteins, *bundle.associations):
            inserted += store.upsert_database_record(record)
        for question in bundle.questions:
            inserted += store.upsert_research_question(question)
        store.commit()

        counts = store.table_counts()
        written = (
            len(bundle.papers) + len(bundle.proteins)
            + len(bundle.associations) + len(bundle.questions)
        )
        updated = written - inserted
        digest = store.content_digest()

    # Proteins vs. associations both live in ``database_records``; report each by
    # the fixture set it came from (idempotent re-ingest keeps these stable).
    return IngestReport(
        db_path=db_path,
        papers=counts["papers"],
        proteins=len(bundle.proteins),
        associations=len(bundle.associations),
        questions=counts["research_questions"],
        inserted=inserted,
        updated=updated,
        digest=digest,
    )


__all__ = ["IngestReport", "ingest_fixtures"]
