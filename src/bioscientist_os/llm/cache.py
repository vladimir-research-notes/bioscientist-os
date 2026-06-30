"""A local, gitignored response cache wrapping any LLM adapter (Milestone 10).

:class:`CachedLLMAdapter` wraps an inner adapter and persists each completion as
canonical JSON under ``<cache_dir>/<provider>/<request_key>.json`` (the real cache
lives under ``data/cache/llm/``, which is gitignored — see ``.gitignore``). It
mirrors :class:`~bioscientist_os.databases.cache.CachedConnector` and exists for
the same two reasons, sharpened by cost:

* **offline-first reproducibility.** Once a request is cached, an identical request
  is served from the local file with no inner call — so a cache warmed from a real
  model keeps working offline and repeated runs are deterministic.
* **honest, free cache hits.** A cache hit is stamped ``data_source = cache``,
  costs **$0** (no token spend), and does not touch the cost guard's budget; a
  cache *miss* delegates to the inner adapter (which prices and charges the call
  normally) and writes a copy for next time. So a cached run of an expensive model
  spends money exactly once.

The cache key is the inner request's content hash (:meth:`LLMRequest.cache_key`),
so the cache is keyed on everything that affects the output (model, system, prompt,
task, ``max_output_tokens``, ``temperature``). The on-disk JSON is sorted-key and
inspectable; tests always point the cache at a temporary directory, and the real
``data/cache/llm/`` is never committed.
"""

from __future__ import annotations

import json
from pathlib import Path

from bioscientist_os.llm.base import (
    LLMAdapter,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)

# Canonical on-disk JSON: sorted keys, indented for inspection, UTF-8.
_CANON = {"sort_keys": True, "ensure_ascii": False, "indent": 2}


class CachedLLMAdapter(LLMAdapter):
    """Wrap an adapter with a read-through JSON cache under ``cache_dir``.

    The wrapped (``inner``) adapter supplies ``name`` / ``provider`` /
    ``default_model`` / ``pricing`` / ``live``, and its :class:`CostGuard` is shared
    (a cache hit simply never charges it). Construct with the directory that should
    hold the cache (``data/cache/llm/`` for real use, a ``tmp_path`` in tests).
    """

    def __init__(self, inner: LLMAdapter, cache_dir: str | Path) -> None:
        self.inner = inner
        self.name = inner.name
        self.provider = inner.provider
        self.default_model = inner.default_model
        self.live = inner.live
        self.pricing = inner.pricing
        self.guard = inner.guard  # shared: spend accounting stays consistent
        self.cache_dir = Path(cache_dir)

    # -- cache layout -----------------------------------------------------

    def _path(self, request: LLMRequest) -> Path:
        return self.cache_dir / self.provider / f"{request.cache_key()}.json"

    def is_cached(self, request: LLMRequest) -> bool:
        """True if ``request`` already has a cache file (no inner call needed)."""
        return self._path(request).is_file()

    def cached_keys(self) -> list[str]:
        """The request keys currently present in the cache directory (sorted)."""
        directory = self.cache_dir / self.provider
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.json"))

    # -- adapter interface ------------------------------------------------

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Serve from the cache if present (free); otherwise delegate and cache.

        A hit returns immediately, stamped ``cache`` with ``cost_usd = 0`` and no
        charge to the guard. A miss runs the inner adapter — which enforces the cost
        guard and charges the real spend — then writes a copy (unless it was a
        dry-run, which produces nothing to cache).
        """
        path = self._path(request)
        if path.is_file():
            return self._load(path, request)

        response = self.inner.generate(request)
        if not response.dry_run:
            self._store(path, response)
        return response

    def _invoke(self, request: LLMRequest, model: str) -> tuple[str, LLMUsage]:
        # generate() is overridden, so this is only reached if a subclass calls it.
        # Delegate to the inner adapter to stay correct.
        return self.inner._invoke(request, model)

    # -- serialization ----------------------------------------------------

    def _store(self, path: Path, response: LLMResponse) -> None:
        record = {
            "text": response.text,
            "model": response.model,
            "adapter": response.adapter,
            "provider": response.provider,
            "live": response.live,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "request_key": response.request_key,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, **_CANON), encoding="utf-8")

    def _load(self, path: Path, request: LLMRequest) -> LLMResponse:
        data = json.loads(path.read_text(encoding="utf-8"))
        usage = data["usage"]
        return LLMResponse(
            text=data["text"],
            model=data["model"],
            usage=LLMUsage(usage["input_tokens"], usage["output_tokens"], estimated=False),
            cost_usd=0.0,  # a cache hit is free — the bytes came from a local file
            adapter=data["adapter"],
            provider=data["provider"],
            live=data["live"],
            request_key=data.get("request_key", request.cache_key()),
            served_from_cache=True,
            dry_run=False,
        )


__all__ = ["CachedLLMAdapter"]
