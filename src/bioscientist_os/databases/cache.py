"""A local, gitignored cache layer wrapping any connector (Milestone 6).

:class:`CachedConnector` wraps an inner connector and persists each fetched record as
canonical JSON under ``data/cache/<source>/<id>.json`` (``data/cache/`` is gitignored
— see ``.gitignore``). It exists for two reasons:

* **offline-first reproducibility.** Once a record is cached, it can be served
  without the inner connector at all — so a cache warmed from a live source keeps
  working with no network, and repeated runs are deterministic.
* **honest provenance.** A *cache hit* is stamped ``data_source = cache`` (the bytes
  came from the local file); a *cache miss* returns the inner connector's own
  ``data_source`` (``fixture`` / ``live`` — the bytes genuinely came from there) and
  writes a ``cache``-stamped copy for next time. So the very first fetch reports
  where the data really came from, and subsequent fetches report ``cache`` — never
  the reverse.

The cache is content only: no timestamps or run ids are written, and the JSON is
sorted-key, so cache files are inspectable and stable. Tests always point the cache
at a temporary directory; the real ``data/cache/`` is never committed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from pydantic import BaseModel

from bioscientist_os.databases.base import BaseConnector, with_data_source
from bioscientist_os.schemas import DataSource

# Canonical on-disk JSON: sorted keys, indented for human inspection, UTF-8.
_CANON = {"sort_keys": True, "ensure_ascii": False, "indent": 2}

# Characters allowed verbatim in a cache filename; anything else is replaced.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(record_id: str) -> str:
    """A filesystem-safe stem for ``record_id`` that stays collision-free.

    Record ids in this project are simple slugs (``P05231``, ``biosci-paper-001``),
    so the sanitized form usually equals the id. When sanitizing *would* change the
    id (an exotic id), a short hash of the original is appended so two distinct ids
    cannot collide onto one file.
    """
    safe = _UNSAFE.sub("_", record_id).strip("_") or "_"
    if safe != record_id:
        suffix = hashlib.sha1(record_id.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe}-{suffix}"
    return safe


class CachedConnector[T: BaseModel](BaseConnector[T]):
    """Wrap a connector with a read-through JSON cache under ``cache_dir``.

    The wrapped (``inner``) connector supplies ``source`` / ``record_type`` /
    ``record_model``; this connector reports ``data_source = cache`` as its layer.
    Construct with the directory that should hold the cache (e.g. ``data/cache/`` for
    real use, a ``tmp_path`` in tests).
    """

    def __init__(self, inner: BaseConnector[T], cache_dir: str | Path) -> None:
        self.inner = inner
        self.source = inner.source
        self.record_type = inner.record_type
        self.record_model = inner.record_model
        self.data_source = DataSource.cache
        self.cache_dir = Path(cache_dir)

    # -- cache layout -----------------------------------------------------

    def _path(self, record_id: str) -> Path:
        return self.cache_dir / self.source / f"{_safe_filename(record_id)}.json"

    def is_cached(self, record_id: str) -> bool:
        """True if ``record_id`` already has a cache file (no inner fetch needed)."""
        return self._path(record_id).is_file()

    def cached_ids(self) -> list[str]:
        """The record ids currently present in the cache directory (sorted).

        Reads each cache file's stored ``record_id`` / ``paper_id`` so the result is
        the true ids, not the (possibly sanitized) filenames.
        """
        directory = self.cache_dir / self.source
        if not directory.is_dir():
            return []
        ids: list[str] = []
        for path in directory.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            ids.append(data.get("record_id") or data.get("paper_id") or path.stem)
        return sorted(ids)

    # -- connector interface ----------------------------------------------

    def fetch(self, record_id: str) -> T | None:
        path = self._path(record_id)
        if path.is_file():
            # Cache hit: the bytes come from the local file, already stamped ``cache``.
            return self.record_model.model_validate_json(path.read_text(encoding="utf-8"))

        record = self.inner.fetch(record_id)
        if record is None:
            return None

        # Cache miss: persist a ``cache``-stamped copy for next time, but return the
        # record with the inner connector's own ``data_source`` (it really came from
        # there just now). Subsequent fetches will hit the file and report ``cache``.
        cached = with_data_source(record, DataSource.cache)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cached.model_dump(mode="json"), **_CANON), encoding="utf-8"
        )
        return record

    def ids(self) -> list[str]:
        # The authoritative id space is the inner connector's (a live inner raises);
        # cached_ids() reports only what has been cached so far.
        return self.inner.ids()


__all__ = ["CachedConnector"]
