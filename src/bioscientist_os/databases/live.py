"""Optional, opt-in live HTTP connectors (Milestone 6) — OFF by default.

The default and test paths never touch the network. A :class:`LiveConnector` is a
thin, clearly-marked option for a user who explicitly opts in, and it is built so
that **no network call can happen unless two conditions are both met**: the
connector is constructed with ``allow_network=True`` *and* its transport actually
performs I/O. The HTTP transport is an injected callable, so:

* in tests, a mock transport exercises the full parse / retry / provenance logic
  **offline** (no sockets, no sleeping — :func:`time.sleep` is injected too); and
* the real default transport (:func:`urllib_transport`, stdlib ``urllib``) is only
  ever reached when a caller has opted in.

Every record a live connector returns is stamped ``data_source = live``. Transient
failures (timeouts, 5xx, 429) are retried with backoff via
:func:`~bioscientist_os.databases.base.call_with_retries`; a ``404`` is reported as
"not found" (``None``), not an error. A live source is **not** enumerable, so
:meth:`LiveConnector.ids` raises.

This module ships one concrete example — :func:`uniprot_live_connector` — to show the
shape of a real adapter. It is best-effort and **never run in CI**; the offline
fixture connectors carry the project's correctness and reproducibility guarantees.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import quote

from pydantic import BaseModel

from bioscientist_os.databases.base import (
    BaseConnector,
    PermanentConnectorError,
    TransientConnectorError,
    call_with_retries,
    with_data_source,
)
from bioscientist_os.schemas import DatabaseRecord, DataSource

# A polite, identifying User-Agent for the opt-in default transport.
_USER_AGENT = "bioscientist-os/0.0.0 (offline-first research workbench; opt-in live mode)"

# Transport contract: given a URL, return the response body as text, or ``None`` for
# a 404 (not found). Raise TransientConnectorError to trigger a retry, or
# PermanentConnectorError for a non-retryable failure.
Transport = Callable[[str], "str | None"]

# A record parser: given the requested id and the raw response body, return a typed
# record, or ``None`` if the body has no usable record (annotated inline on
# ``LiveConnector.__init__`` as ``Callable[[str, str], T | None]``).


def urllib_transport(url: str, *, timeout: float = 10.0) -> str | None:
    """Stdlib HTTP GET. OPT-IN ONLY — never reached in tests or the default path.

    Maps the network outcome onto the connector error contract: a ``404`` becomes
    ``None`` (not found); timeouts / connection errors / 429 / 5xx become a
    retryable :class:`TransientConnectorError`; any other HTTP error becomes a
    non-retryable :class:`PermanentConnectorError`.
    """
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (429, 500, 502, 503, 504):
            raise TransientConnectorError(f"HTTP {exc.code} for {url}") from exc
        raise PermanentConnectorError(f"HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TransientConnectorError(f"transport error for {url}: {exc}") from exc


class LiveConnector[T: BaseModel](BaseConnector[T]):
    """An opt-in HTTP connector. Disabled unless ``allow_network=True``.

    With ``allow_network=False`` (the default), :meth:`fetch` raises a
    :class:`PermanentConnectorError` *before* the transport is consulted, so simply
    constructing one is inert. The ``url_template`` is formatted with the
    URL-quoted id (``{id}``); ``parse`` turns the raw body into a typed record.
    """

    def __init__(
        self,
        source: str,
        record_type: str,
        url_template: str,
        parse: Callable[[str, str], T | None],
        record_model: type[T],
        *,
        allow_network: bool = False,
        transport: Transport = urllib_transport,
        retries: int = 2,
        base_delay: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.source = source
        self.record_type = record_type
        self.record_model = record_model
        self.data_source = DataSource.live
        self.url_template = url_template
        self._parse = parse
        self.allow_network = allow_network
        self._transport = transport
        self._retries = retries
        self._base_delay = base_delay
        self._sleep = sleep

    def url_for(self, record_id: str) -> str:
        """The request URL for ``record_id`` (id is URL-quoted)."""
        return self.url_template.format(id=quote(record_id, safe=""))

    def fetch(self, record_id: str) -> T | None:
        if not self.allow_network:
            raise PermanentConnectorError(
                f"{self.source} live connector is disabled (offline-first default); "
                "construct it with allow_network=True to opt in"
            )
        url = self.url_for(record_id)
        body = call_with_retries(
            lambda: self._transport(url),
            retries=self._retries,
            base_delay=self._base_delay,
            sleep=self._sleep,
            retry_on=(TransientConnectorError,),
        )
        if body is None:
            return None
        record = self._parse(record_id, body)
        if record is None:
            return None
        return with_data_source(record, DataSource.live)

    def ids(self) -> list[str]:
        raise PermanentConnectorError(
            f"{self.source} live connector is not enumerable (no local id list)"
        )


# ---------------------------------------------------------------------------
# Concrete example: UniProt (best-effort, opt-in, never run in CI)
# ---------------------------------------------------------------------------

# The official UniProtKB single-entry JSON endpoint. Used only when a caller opts in.
UNIPROT_LIVE_URL = "https://rest.uniprot.org/uniprotkb/{id}.json"


def parse_uniprot_json(record_id: str, body: str) -> DatabaseRecord | None:
    """Parse a UniProtKB JSON entry into a :class:`DatabaseRecord` (best-effort).

    Pulls a small, stable subset (accession, recommended protein name, primary gene,
    organism) into ``fields`` to mirror the fixture protein records' shape. Defensive
    by design: missing keys degrade to ``None``/absent rather than raising, because
    this is opt-in code that is not exercised in tests.
    """
    import json

    data = json.loads(body)
    if not isinstance(data, dict):
        return None
    accession = data.get("primaryAccession") or record_id

    protein = data.get("proteinDescription") or {}
    rec_name = (protein.get("recommendedName") or {}).get("fullName") or {}
    protein_name = rec_name.get("value")

    genes = data.get("genes") or []
    gene = (genes[0].get("geneName") or {}).get("value") if genes else None

    organism = (data.get("organism") or {}).get("scientificName")

    fields: dict[str, object] = {"accession": accession}
    if protein_name:
        fields["protein_name"] = protein_name
    if gene:
        fields["gene"] = gene
    if organism:
        fields["organism"] = organism

    return DatabaseRecord(
        record_id=accession,
        source="UniProt",
        record_type="protein",
        fields=fields,
        data_source=DataSource.live,
        synthetic=False,
    )


def uniprot_live_connector(
    *,
    allow_network: bool = False,
    transport: Transport = urllib_transport,
    **kwargs: object,
) -> LiveConnector[DatabaseRecord]:
    """An opt-in live UniProt connector (off by default; never used in tests).

    Disabled unless ``allow_network=True``. Provided to show the shape of a real
    adapter — the offline :func:`~bioscientist_os.databases.fixture.uniprot_connector`
    is the one the project actually relies on.
    """
    return LiveConnector(
        source="UniProt",
        record_type="protein",
        url_template=UNIPROT_LIVE_URL,
        parse=parse_uniprot_json,
        record_model=DatabaseRecord,
        allow_network=allow_network,
        transport=transport,
        **kwargs,  # type: ignore[arg-type]
    )


__all__ = [
    "Transport",
    "urllib_transport",
    "LiveConnector",
    "UNIPROT_LIVE_URL",
    "parse_uniprot_json",
    "uniprot_live_connector",
]
