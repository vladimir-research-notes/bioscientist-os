"""Fixture ingestion (Milestone 2).

Reads the small, clearly-labeled corpora under ``data/fixtures/`` (via the
parse-only loader in :mod:`bioscientist_os.fixtures`) and writes them into a local
SQLite database through :class:`bioscientist_os.storage.SQLiteStore`, attaching
``data_source`` provenance. Writes are idempotent and the resulting database is
content-deterministic.

The entry point is :func:`ingest_fixtures`; :class:`IngestReport` describes what a
run wrote.
"""

from __future__ import annotations

from bioscientist_os.ingest.pipeline import IngestReport, ingest_fixtures

__all__ = ["IngestReport", "ingest_fixtures"]
