"""Fixture-backed connectors — the required, offline-first adapters (Milestone 6).

A :class:`FixtureConnector` serves committed records (already ingested or loaded
from ``data/fixtures/``) by id, stamping every result ``data_source = fixture``. It
is the **default and only** connector on the offline path: tests and the documented
end-to-end run never need the cache or a live source.

Three concrete connectors cover the corpus, matching the ``docs/PLAN.md`` minimum
("fixture-backed UniProt-style and paper-metadata connectors") plus the Open
Targets associations:

* :func:`uniprot_connector` — UniProt-style protein
  :class:`~bioscientist_os.schemas.DatabaseRecord`\\s, keyed by accession;
* :func:`opentargets_connector` — Open Targets-style association records, keyed by
  their record id;
* :func:`paper_connector` — paper-metadata, serving the corpus
  :class:`~bioscientist_os.schemas.Paper`\\s by ``paper_id`` (the offline stand-in
  for a PubMed / Europe PMC connector).

:func:`build_fixture_connectors` assembles all three from a corpus
(``papers`` + ``database_records``); the registry layer
(:mod:`bioscientist_os.databases.registry`) wraps them for the CLI.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from bioscientist_os.databases.base import BaseConnector, with_data_source
from bioscientist_os.schemas import DatabaseRecord, DataSource, Paper

# The originating-database names, as they appear in ``DatabaseRecord.source`` and in
# the fixtures. ``PAPERS_SOURCE`` is the logical source for the paper-metadata
# connector (the offline stand-in for PubMed / Europe PMC).
UNIPROT_SOURCE = "UniProt"
OPENTARGETS_SOURCE = "OpenTargets"
PAPERS_SOURCE = "papers"


class FixtureConnector[T: (Paper, DatabaseRecord)](BaseConnector[T]):
    """An in-memory connector over a fixed set of committed records.

    Built from an iterable of records plus a ``key`` that extracts each record's id.
    Every record is stamped ``data_source = fixture`` at construction, so the
    connector's contract holds regardless of the inputs' incoming labels. On an id
    collision the first record wins (a documented, stable rule), mirroring the
    storage layer's primary keys.
    """

    def __init__(
        self,
        source: str,
        record_type: str,
        records: Iterable[T],
        *,
        key: Callable[[T], str],
        record_model: type[T],
    ) -> None:
        self.source = source
        self.record_type = record_type
        self.record_model = record_model
        self.data_source = DataSource.fixture
        self._by_id: dict[str, T] = {}
        for record in records:
            stamped = with_data_source(record, DataSource.fixture)
            self._by_id.setdefault(key(stamped), stamped)

    def fetch(self, record_id: str) -> T | None:
        return self._by_id.get(record_id)

    def ids(self) -> list[str]:
        return sorted(self._by_id)


def uniprot_connector(
    records: Iterable[DatabaseRecord], *, source: str = UNIPROT_SOURCE
) -> FixtureConnector[DatabaseRecord]:
    """A protein connector over the UniProt-style records in ``records`` (by accession)."""
    proteins = [r for r in records if r.source == source]
    return FixtureConnector(
        source, "protein", proteins, key=lambda r: r.record_id, record_model=DatabaseRecord
    )


def opentargets_connector(
    records: Iterable[DatabaseRecord], *, source: str = OPENTARGETS_SOURCE
) -> FixtureConnector[DatabaseRecord]:
    """An association connector over the Open Targets-style records in ``records``."""
    associations = [r for r in records if r.source == source]
    return FixtureConnector(
        source, "association", associations, key=lambda r: r.record_id, record_model=DatabaseRecord
    )


def paper_connector(papers: Iterable[Paper]) -> FixtureConnector[Paper]:
    """A paper-metadata connector over the corpus papers, keyed by ``paper_id``."""
    return FixtureConnector(
        PAPERS_SOURCE, "paper", papers, key=lambda p: p.paper_id, record_model=Paper
    )


def build_fixture_connectors(
    papers: Iterable[Paper], db_records: Iterable[DatabaseRecord]
) -> dict[str, BaseConnector]:
    """Build the standard fixture connectors keyed by short CLI name.

    ``db_records`` is the full, mixed list of database records (UniProt + Open
    Targets); each connector filters it by ``source``. Returns
    ``{"uniprot": ..., "opentargets": ..., "papers": ...}``.
    """
    db_records = list(db_records)
    return {
        "uniprot": uniprot_connector(db_records),
        "opentargets": opentargets_connector(db_records),
        "papers": paper_connector(papers),
    }


__all__ = [
    "UNIPROT_SOURCE",
    "OPENTARGETS_SOURCE",
    "PAPERS_SOURCE",
    "FixtureConnector",
    "uniprot_connector",
    "opentargets_connector",
    "paper_connector",
    "build_fixture_connectors",
]
