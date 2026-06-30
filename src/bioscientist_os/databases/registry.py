"""Connector registry and fixture / database entry points (Milestone 6).

A :class:`ConnectorRegistry` is a small, named collection of connectors with the
lookups the CLI needs (``names``, ``get``, ``describe``). Two entry points build one:

* :func:`load_connectors` — from the committed ``data/fixtures/`` (no database
  required); and
* :func:`open_connectors` — from an ingested SQLite database (the path
  ``biosci db`` takes), with the same "not a bioscientist-os database" guard as the
  other subcommands.

Both produce the same three fixture connectors (``uniprot``, ``opentargets``,
``papers``). Live connectors are deliberately *not* registered here: they are opt-in
and constructed explicitly by a caller (see
:mod:`bioscientist_os.databases.live`), never returned by default.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bioscientist_os.databases.base import BaseConnector, ConnectorError
from bioscientist_os.databases.fixture import build_fixture_connectors
from bioscientist_os.schemas import DatabaseRecord, Paper


@dataclass(frozen=True)
class ConnectorRegistry:
    """A named set of connectors, addressable by short CLI name (``uniprot``, …)."""

    connectors: dict[str, BaseConnector]

    def names(self) -> list[str]:
        """The registered connector names, sorted."""
        return sorted(self.connectors)

    def __contains__(self, name: object) -> bool:
        return name in self.connectors

    def __getitem__(self, name: str) -> BaseConnector:
        return self.get(name)

    def get(self, name: str) -> BaseConnector:
        """Return the connector named ``name`` or raise ``KeyError(name)``."""
        try:
            return self.connectors[name]
        except KeyError:
            raise KeyError(name) from None

    def describe(self) -> list[dict[str, object]]:
        """One :meth:`BaseConnector.describe` row per connector, in name order.

        Each row gains a ``name`` key. ``count`` is ``None`` for any non-enumerable
        connector (never the case for the default fixture set).
        """
        rows: list[dict[str, object]] = []
        for name in self.names():
            row: dict[str, object] = {"name": name}
            connector = self.connectors[name]
            try:
                row.update(connector.describe())
            except ConnectorError:  # pragma: no cover - fixture connectors enumerate
                row.update(
                    {
                        "source": connector.source,
                        "record_type": connector.record_type,
                        "data_source": connector.data_source.value,
                        "count": None,
                    }
                )
            rows.append(row)
        return rows


def connectors_from_records(
    papers: Iterable[Paper], db_records: Iterable[DatabaseRecord]
) -> ConnectorRegistry:
    """Build the default fixture-connector registry from an in-memory corpus."""
    return ConnectorRegistry(build_fixture_connectors(papers, db_records))


def load_connectors(fixtures_root: str | Path | None = None) -> ConnectorRegistry:
    """Build the registry from the committed fixtures (no database needed)."""
    from bioscientist_os import fixtures

    bundle = fixtures.load_all(fixtures_root)
    return connectors_from_records(bundle.papers, bundle.proteins + bundle.associations)


def open_connectors(db_path: str | Path) -> ConnectorRegistry:
    """Build the registry from an ingested SQLite database.

    Raises :class:`ValueError` if ``db_path`` is not a bioscientist-os database
    (no ingested tables), mirroring the other database-backed subcommands.
    """
    from bioscientist_os.storage import SQLiteStore

    with SQLiteStore(db_path) as store:
        if not store.is_initialized():
            raise ValueError(f"{db_path} is not a bioscientist-os database (no ingested tables)")
        papers = list(store.iter_papers())
        records = list(store.iter_database_records())
    return connectors_from_records(papers, records)


__all__ = [
    "ConnectorRegistry",
    "connectors_from_records",
    "load_connectors",
    "open_connectors",
]
