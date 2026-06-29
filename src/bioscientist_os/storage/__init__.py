"""Local persistence (Milestone 2).

SQLite by default (stdlib ``sqlite3``, deterministic file output); DuckDB is an
optional backend. Stores ingested papers, entities, claims, links, and evidence
tables with their provenance fields. Empty at Milestone 0.
"""

from __future__ import annotations
