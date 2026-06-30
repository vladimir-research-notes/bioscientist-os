"""Connector foundations: the base interface, errors, retry, and provenance stamping.

This module is the offline-first contract every connector implements (Milestone 6).
A *connector* hides **where** a record physically comes from — a committed fixture,
a local cache, or a live API — behind one small interface, and guarantees that every
record it hands back carries an honest ``data_source`` (``fixture`` / ``cache`` /
``live``). Downstream, an evidence-table cell or a memo can therefore always show
whether a database link is committed, cached, or freshly fetched, instead of
trusting an opaque blob.

Three pieces live here, all dependency-light (stdlib + the schemas):

* :class:`BaseConnector` — the abstract interface (look a record up by id, with
  provenance). Concrete adapters are :class:`~bioscientist_os.databases.fixture.FixtureConnector`
  (required), :class:`~bioscientist_os.databases.cache.CachedConnector`, and the
  opt-in :class:`~bioscientist_os.databases.live.LiveConnector`.
* the connector exception hierarchy (:class:`ConnectorError` and its transient /
  permanent subclasses, plus :class:`RecordNotFound`), so retry/error handling is
  explicit and a missing id is distinguishable from an operational failure.
* :func:`call_with_retries` — a small, deterministic, **injectable-sleep**
  exponential-backoff helper used by the live path. It is fully testable offline
  (the live connectors are never exercised against a real network in tests).

Provenance is stamped, never passed through: :func:`with_data_source` returns a copy
of a record with its ``data_source`` set, so a ``FixtureConnector`` always reports
``fixture`` and a cache hit always reports ``cache`` regardless of what the
underlying object happened to carry.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from pydantic import BaseModel

from bioscientist_os.schemas import DataSource

# Connectors are generic over the record type they return — both
# :class:`~bioscientist_os.schemas.Paper` and
# :class:`~bioscientist_os.schemas.DatabaseRecord` carry the ``data_source`` field a
# connector stamps, so the type parameter is bound to ``BaseModel`` (see the PEP 695
# ``[T: BaseModel]`` parameters on :class:`BaseConnector` and :func:`with_data_source`).


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConnectorError(RuntimeError):
    """An operational failure in a connector (transport error, exhausted retries).

    Distinct from :class:`RecordNotFound`: this is "the lookup could not be
    performed", not "the lookup ran and the id is absent".
    """


class TransientConnectorError(ConnectorError):
    """A retryable failure: a timeout, a 5xx, or a rate-limit response.

    :func:`call_with_retries` retries these (with backoff) up to its bound; a live
    transport raises this for failures worth retrying.
    """


class PermanentConnectorError(ConnectorError):
    """A non-retryable failure: a malformed request, or a disabled connector.

    Never retried by :func:`call_with_retries`; it propagates on the first raise.
    """


class RecordNotFound(KeyError):
    """Raised by :meth:`BaseConnector.get` when a record id is absent from a source.

    A ``KeyError`` (not a :class:`ConnectorError`): the source answered, and the id
    simply is not there. ``fetch`` returns ``None`` for the same case; ``get`` is the
    raise-on-miss variant.
    """

    def __init__(self, source: str, record_id: str) -> None:
        super().__init__(record_id)
        self.source = source
        self.record_id = record_id

    def __str__(self) -> str:
        return f"no record {self.record_id!r} in source {self.source!r}"


# ---------------------------------------------------------------------------
# Provenance stamping
# ---------------------------------------------------------------------------


def with_data_source[T: BaseModel](record: T, data_source: DataSource) -> T:
    """Return ``record`` with its ``data_source`` set (copy only if it would change).

    This is how connectors enforce their provenance contract rather than trusting an
    object's incoming label: a fixture connector stamps ``fixture``, a cache hit
    stamps ``cache``, a live fetch stamps ``live``. ``synthetic`` is left untouched —
    *fabricated-vs-real* is an orthogonal axis to *where the bytes came from*.

    Works for any record model with a ``data_source`` field
    (:class:`~bioscientist_os.schemas.Paper`,
    :class:`~bioscientist_os.schemas.DatabaseRecord`).
    """
    if record.data_source == data_source:  # type: ignore[attr-defined]
        return record
    return record.model_copy(update={"data_source": data_source})


# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------


def call_with_retries[R](
    fn: Callable[[], R],
    *,
    retries: int = 2,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    retry_on: tuple[type[BaseException], ...] = (TransientConnectorError,),
) -> R:
    """Call ``fn`` with bounded exponential-backoff retries on *transient* errors.

    Retries only exceptions in ``retry_on`` (transient ones by default); any other
    exception propagates immediately and unwrapped. After ``retries`` retries are
    exhausted the last transient error is wrapped in a :class:`ConnectorError`.

    Backoff for retry ``i`` (0-indexed) is ``min(max_delay, base_delay * 2**i)``.
    ``sleep`` is injected so the schedule is deterministic and tests run instantly
    (pass a no-op spy); the live path uses the real :func:`time.sleep`.

    ``retries=0`` calls ``fn`` exactly once. Returns ``fn``'s value on success.
    """
    if retries < 0:
        raise ValueError("retries must be >= 0")
    last_exc: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if attempt == retries:
                break
            delay = min(max_delay, base_delay * (2**attempt))
            if delay > 0:
                sleep(delay)
    raise ConnectorError(
        f"call failed after {retries + 1} attempt(s): {last_exc}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Base connector
# ---------------------------------------------------------------------------


class BaseConnector[T: BaseModel](ABC):
    """Abstract connector: look up provenance-stamped records by id.

    Subclasses implement exactly two methods:

    * :meth:`fetch` — return the record for ``record_id``, or ``None`` if absent;
    * :meth:`ids` — the connector's enumerable id space (a fixture/cache lists its
      ids; a live source raises, since it has no finite, local id list).

    Everything else (:meth:`get`, :meth:`fetch_many`, ``in``, ``len``,
    :meth:`describe`) is built on those two. Concrete attributes ``source`` (the
    originating database name, e.g. ``"UniProt"``), ``record_type`` (e.g.
    ``"protein"``), ``record_model`` (the pydantic type returned), and
    ``data_source`` (the layer this connector represents) are set by subclasses.
    """

    source: str
    record_type: str
    record_model: type[T]
    data_source: DataSource

    @abstractmethod
    def fetch(self, record_id: str) -> T | None:
        """Return the record for ``record_id``, or ``None`` if the source lacks it."""

    @abstractmethod
    def ids(self) -> list[str]:
        """Return the enumerable id space (sorted), or raise if not enumerable."""

    def get(self, record_id: str) -> T:
        """Return the record for ``record_id`` or raise :class:`RecordNotFound`."""
        record = self.fetch(record_id)
        if record is None:
            raise RecordNotFound(self.source, record_id)
        return record

    def fetch_many(self, record_ids: Iterable[str]) -> list[T]:
        """Fetch several ids, silently dropping the ones that are absent.

        Order follows ``record_ids``. Use :meth:`get` when a missing id should raise.
        """
        out: list[T] = []
        for record_id in record_ids:
            record = self.fetch(record_id)
            if record is not None:
                out.append(record)
        return out

    def __contains__(self, record_id: object) -> bool:
        return isinstance(record_id, str) and self.fetch(record_id) is not None

    def __len__(self) -> int:
        return len(self.ids())

    def describe(self) -> dict[str, object]:
        """A small, inspectable summary of the connector for the CLI and tests.

        ``count`` is the size of the id space, or ``None`` for a non-enumerable
        (live) source.
        """
        try:
            count: int | None = len(self.ids())
        except ConnectorError:
            count = None
        return {
            "source": self.source,
            "record_type": self.record_type,
            "data_source": self.data_source.value,
            "count": count,
        }


__all__ = [
    "ConnectorError",
    "TransientConnectorError",
    "PermanentConnectorError",
    "RecordNotFound",
    "with_data_source",
    "call_with_retries",
    "BaseConnector",
]
