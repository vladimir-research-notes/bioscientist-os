"""SQLite persistence for the ingested fixture corpus (Milestone 2).

The default, stdlib-only storage backend (DuckDB is a possible optional backend
later; it is not required and not implemented here). The design follows three
rules so the database is auditable and reproducible:

* **One row per schema object.** ``papers``, ``database_records``, and
  ``research_questions`` map one-to-one to the :mod:`bioscientist_os.schemas`
  models. Structured sub-fields (authors, keywords, external ids, database-record
  payloads) are stored as *canonical* (sorted-key, compact) JSON text, so a
  stored record reconstructs back into its exact pydantic model — see
  :meth:`SQLiteStore.iter_papers` and the round-trip tests.
* **Idempotent writes.** Every write is an UPSERT keyed by the object's stable id
  (``paper_id``; ``(source, record_id)``; ``question_id``). Re-ingesting the same
  fixtures updates rows in place and never creates duplicates.
* **Content-deterministic.** No timestamps, run ids, or other run-varying data
  are written to the data tables, and reads/digests sort explicitly by primary
  key. A database built from fixed fixtures therefore has a stable
  :meth:`SQLiteStore.content_digest`, independent of insertion order or the
  on-disk page layout. (Raw file *bytes* can still vary across libsqlite
  versions; the digest is the robust, logical determinism guarantee.)

Provenance discipline: ingested papers and database records are *observed
metadata* — directly read from a source record. Their ``data_source`` (here
always ``fixture``) and ``synthetic`` flag are stored as first-class columns, not
buried in a blob.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bioscientist_os import __version__
from bioscientist_os.schemas import (
    DatabaseRecord,
    DataSource,
    Paper,
    ResearchQuestion,
)

# Bump only on a breaking change to the table layout. Written to the SQLite header
# (PRAGMA user_version) and to the ``ingest_meta`` table, and folded into the
# content digest so a schema change is never mistaken for identical content.
SCHEMA_VERSION = 1

# A stable, self-identifying tag for the SQLite header (PRAGMA application_id):
# the bytes of "BSOS" read as a big-endian 32-bit integer.
APPLICATION_ID = 0x42534F53

# Canonical JSON: sorted keys + compact separators, so the stored text (and thus
# the content digest) is deterministic regardless of dict iteration order.
_CANON: dict[str, Any] = {"sort_keys": True, "ensure_ascii": False, "separators": (",", ":")}

# The data tables that make up the ingested corpus, with the column to sort by
# for deterministic reads and digests. ``ingest_meta`` is deliberately excluded
# from the digest so the digest is a pure function of the fixtures + schema.
_DATA_TABLES: tuple[tuple[str, str], ...] = (
    ("papers", "paper_id"),
    ("database_records", "source, record_id"),
    ("research_questions", "question_id"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    paper_id          TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    journal           TEXT,
    year              INTEGER,
    abstract          TEXT NOT NULL,
    url               TEXT,
    authors_json      TEXT NOT NULL,
    keywords_json     TEXT NOT NULL,
    external_ids_json TEXT NOT NULL,
    data_source       TEXT NOT NULL,
    synthetic         INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS database_records (
    source      TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    record_type TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    data_source TEXT NOT NULL,
    synthetic   INTEGER NOT NULL,
    PRIMARY KEY (source, record_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS research_questions (
    question_id               TEXT PRIMARY KEY,
    text                      TEXT NOT NULL,
    entities_of_interest_json TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ingest_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;
"""


def _dumps(obj: Any) -> str:
    """Serialize to canonical JSON (sorted keys, compact, UTF-8)."""
    return json.dumps(obj, **_CANON)


class SQLiteStore:
    """A thin, deterministic SQLite wrapper for the ingested corpus.

    Use as a context manager so the connection is always closed::

        with SQLiteStore(path) as store:
            store.initialize()
            store.upsert_paper(paper)
            store.commit()

    The class does not load fixtures or decide *what* to write — that is the
    ingestion pipeline's job (:mod:`bioscientist_os.ingest`). It only persists and
    reads back typed objects.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> SQLiteStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    def commit(self) -> None:
        self._conn.commit()

    def initialize(self) -> None:
        """Create tables and stamp the header/meta. Safe to call repeatedly."""
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        # Meta records the schema and package version. These are fixed for a given
        # code revision, so they do not undermine determinism; they are excluded
        # from content_digest() (which covers ingested data only).
        self._set_meta("schema_version", str(SCHEMA_VERSION))
        self._set_meta("bioscientist_os_version", __version__)
        self._conn.commit()

    def is_initialized(self) -> bool:
        """True if the expected data tables exist (i.e. the file is our database)."""
        names = {row["name"] for row in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        return {"papers", "database_records", "research_questions"} <= names

    # -- writes (idempotent upserts) --------------------------------------

    def upsert_paper(self, paper: Paper) -> bool:
        """Insert or update one paper. Returns ``True`` iff the row was new."""
        existed = self._exists("SELECT 1 FROM papers WHERE paper_id = ?", (paper.paper_id,))
        self._conn.execute(
            """
            INSERT INTO papers
              (paper_id, title, journal, year, abstract, url,
               authors_json, keywords_json, external_ids_json, data_source, synthetic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id) DO UPDATE SET
              title=excluded.title, journal=excluded.journal, year=excluded.year,
              abstract=excluded.abstract, url=excluded.url,
              authors_json=excluded.authors_json, keywords_json=excluded.keywords_json,
              external_ids_json=excluded.external_ids_json,
              data_source=excluded.data_source, synthetic=excluded.synthetic
            """,
            (
                paper.paper_id,
                paper.title,
                paper.journal,
                paper.year,
                paper.abstract,
                paper.url,
                _dumps([a.model_dump() for a in paper.authors]),
                _dumps(list(paper.keywords)),
                _dumps(dict(paper.external_ids)),
                paper.data_source.value,
                1 if paper.synthetic else 0,
            ),
        )
        return not existed

    def upsert_database_record(self, record: DatabaseRecord) -> bool:
        """Insert or update one database record. Returns ``True`` iff the row was new."""
        existed = self._exists(
            "SELECT 1 FROM database_records WHERE source = ? AND record_id = ?",
            (record.source, record.record_id),
        )
        self._conn.execute(
            """
            INSERT INTO database_records
              (source, record_id, record_type, fields_json, data_source, synthetic)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, record_id) DO UPDATE SET
              record_type=excluded.record_type, fields_json=excluded.fields_json,
              data_source=excluded.data_source, synthetic=excluded.synthetic
            """,
            (
                record.source,
                record.record_id,
                record.record_type,
                _dumps(record.fields),
                record.data_source.value,
                1 if record.synthetic else 0,
            ),
        )
        return not existed

    def upsert_research_question(self, question: ResearchQuestion) -> bool:
        """Insert or update one research question. Returns ``True`` iff the row was new."""
        existed = self._exists(
            "SELECT 1 FROM research_questions WHERE question_id = ?", (question.question_id,)
        )
        self._conn.execute(
            """
            INSERT INTO research_questions (question_id, text, entities_of_interest_json)
            VALUES (?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
              text=excluded.text,
              entities_of_interest_json=excluded.entities_of_interest_json
            """,
            (
                question.question_id,
                question.text,
                _dumps(list(question.entities_of_interest)),
            ),
        )
        return not existed

    # -- reads (round-trip back into typed objects) -----------------------

    def iter_papers(self) -> Iterator[Paper]:
        for r in self._conn.execute("SELECT * FROM papers ORDER BY paper_id"):
            yield Paper(
                paper_id=r["paper_id"],
                title=r["title"],
                journal=r["journal"],
                year=r["year"],
                abstract=r["abstract"],
                url=r["url"],
                authors=json.loads(r["authors_json"]),
                keywords=json.loads(r["keywords_json"]),
                external_ids=json.loads(r["external_ids_json"]),
                data_source=DataSource(r["data_source"]),
                synthetic=bool(r["synthetic"]),
            )

    def iter_database_records(self) -> Iterator[DatabaseRecord]:
        for r in self._conn.execute(
            "SELECT * FROM database_records ORDER BY source, record_id"
        ):
            yield DatabaseRecord(
                record_id=r["record_id"],
                source=r["source"],
                record_type=r["record_type"],
                fields=json.loads(r["fields_json"]),
                data_source=DataSource(r["data_source"]),
                synthetic=bool(r["synthetic"]),
            )

    def iter_research_questions(self) -> Iterator[ResearchQuestion]:
        for r in self._conn.execute(
            "SELECT * FROM research_questions ORDER BY question_id"
        ):
            yield ResearchQuestion(
                question_id=r["question_id"],
                text=r["text"],
                entities_of_interest=json.loads(r["entities_of_interest_json"]),
            )

    # -- aggregate views --------------------------------------------------

    def table_counts(self) -> dict[str, int]:
        """Row count per data table (``papers``/``database_records``/``research_questions``)."""
        return {
            table: self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table, _ in _DATA_TABLES
        }

    def record_breakdown(self) -> list[tuple[str, str, int]]:
        """``database_records`` counts grouped by ``(source, record_type)``, sorted."""
        rows = self._conn.execute(
            "SELECT source, record_type, COUNT(*) AS n FROM database_records "
            "GROUP BY source, record_type ORDER BY source, record_type"
        )
        return [(r["source"], r["record_type"], r["n"]) for r in rows]

    def meta(self) -> dict[str, str]:
        """All ``ingest_meta`` key/value pairs."""
        rows = self._conn.execute("SELECT key, value FROM ingest_meta")
        return {r["key"]: r["value"] for r in rows}

    def content_digest(self) -> str:
        """SHA-256 over the canonical serialization of every data row, sorted by id.

        A pure function of the ingested content + :data:`SCHEMA_VERSION`,
        independent of insertion order and on-disk layout. Two databases with the
        same digest hold the same corpus; the ingestion pipeline uses this to
        assert deterministic, idempotent builds.
        """
        h = hashlib.sha256()
        h.update(f"schema_version={SCHEMA_VERSION}\n".encode())
        for table, order in _DATA_TABLES:
            h.update(f"#table:{table}\n".encode())
            for row in self._conn.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                payload = {key: row[key] for key in row.keys()}
                h.update((_dumps(payload) + "\n").encode())
        return h.hexdigest()

    # -- internals --------------------------------------------------------

    def _exists(self, sql: str, params: tuple[Any, ...]) -> bool:
        return self._conn.execute(sql, params).fetchone() is not None

    def _set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO ingest_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


__all__ = ["SQLiteStore", "SCHEMA_VERSION", "APPLICATION_ID"]
