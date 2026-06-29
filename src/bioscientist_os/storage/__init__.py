"""Local persistence (Milestone 2).

SQLite by default (stdlib :mod:`sqlite3`, deterministic file output); DuckDB is a
possible optional backend later, not required and not implemented yet. Stores the
ingested papers, database records, and research questions with their provenance
columns (``data_source`` / ``synthetic``). Entities, claims, and evidence tables
are persisted in later milestones.

The concrete backend is :class:`SQLiteStore`; ingestion writes through it.
"""

from __future__ import annotations

from bioscientist_os.storage.sqlite_store import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    SQLiteStore,
)

__all__ = ["SQLiteStore", "SCHEMA_VERSION", "APPLICATION_ID"]
