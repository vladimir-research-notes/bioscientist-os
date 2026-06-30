"""Offline-first database connector layer (Milestone 6).

A small adapter layer that hides **where** a record comes from behind one interface
and keeps an honest ``data_source`` (``fixture`` / ``cache`` / ``live``) on every
record it returns::

    BaseConnector
      ├── FixtureConnector   committed records  -> data_source=fixture   [required]
      ├── CachedConnector    read-through cache  -> data_source=cache     (data/cache/, gitignored)
      └── LiveConnector      opt-in HTTP         -> data_source=live      [opt-in, off by default]

The default and test paths use only the fixture connectors (``uniprot``,
``opentargets``, ``papers``); the cache makes repeated runs deterministic and
network-free; live connectors are opt-in and never required for tests. See
:mod:`bioscientist_os.databases.base` for the interface, errors, and the retry
helper, and ``docs/DATABASES.md`` for the design and limitations.
"""

from __future__ import annotations

from bioscientist_os.databases.base import (
    BaseConnector,
    ConnectorError,
    PermanentConnectorError,
    RecordNotFound,
    TransientConnectorError,
    call_with_retries,
    with_data_source,
)
from bioscientist_os.databases.cache import CachedConnector
from bioscientist_os.databases.fixture import (
    OPENTARGETS_SOURCE,
    PAPERS_SOURCE,
    UNIPROT_SOURCE,
    FixtureConnector,
    build_fixture_connectors,
    opentargets_connector,
    paper_connector,
    uniprot_connector,
)
from bioscientist_os.databases.live import (
    LiveConnector,
    parse_uniprot_json,
    uniprot_live_connector,
    urllib_transport,
)
from bioscientist_os.databases.registry import (
    ConnectorRegistry,
    connectors_from_records,
    load_connectors,
    open_connectors,
)

__all__ = [
    # base
    "BaseConnector",
    "ConnectorError",
    "TransientConnectorError",
    "PermanentConnectorError",
    "RecordNotFound",
    "with_data_source",
    "call_with_retries",
    # fixture
    "FixtureConnector",
    "uniprot_connector",
    "opentargets_connector",
    "paper_connector",
    "build_fixture_connectors",
    "UNIPROT_SOURCE",
    "OPENTARGETS_SOURCE",
    "PAPERS_SOURCE",
    # cache
    "CachedConnector",
    # live (opt-in)
    "LiveConnector",
    "urllib_transport",
    "uniprot_live_connector",
    "parse_uniprot_json",
    # registry
    "ConnectorRegistry",
    "connectors_from_records",
    "load_connectors",
    "open_connectors",
]
