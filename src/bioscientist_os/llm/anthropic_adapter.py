"""Optional, opt-in Anthropic LLM adapter (Milestone 10) — OFF by default.

The default and test paths never reach this module's network code. It is the LLM
analogue of the opt-in :mod:`bioscientist_os.databases.live` connector: a thin,
clearly-marked example of a *real* adapter that is built so **no network call can
happen unless two conditions both hold** — the adapter is constructed with
``allow_network=True`` *and* its client actually performs I/O. The Anthropic
client is an injected dependency, so:

* in tests, a tiny fake client exercises the full parse / usage / provenance logic
  **offline** (no sockets, no ``anthropic`` package needed); and
* the real client (``anthropic.Anthropic``) is imported **lazily** and only ever
  built when a caller has opted in and supplied an API key.

Two deliberate honesty choices, both consistent with the project's ethos:

* **Pricing is required, never hardcoded.** A cost guard is only honest if its
  prices are current, and vendor prices drift. This adapter therefore requires the
  caller to pass a :class:`~bioscientist_os.llm.base.Pricing` explicitly (from the
  current Anthropic pricing page). :data:`ILLUSTRATIVE_PRICING` is provided purely
  as a labeled convenience and is **not** guaranteed current — verify before use.
* **Model output is least-trusted.** Every response is stamped
  ``data_source = live`` and enters the system as an *unsupported hypothesis*
  (inherited from :class:`~bioscientist_os.llm.base.LLMResponse`); it never
  replaces a transparent baseline (see ``docs/SAFETY.md``).

This adapter is best-effort and **never run in CI**; the mock adapter carries the
project's correctness and reproducibility guarantees. Model ids below are the
current Claude family; pass whichever the caller has access to.
"""

from __future__ import annotations

from typing import Any

from bioscientist_os.llm.base import (
    CostGuard,
    LLMAdapter,
    LLMDisabledError,
    LLMError,
    LLMRequest,
    LLMUsage,
    Pricing,
)

# Current Claude model ids (pass the one the caller has access to). The default is
# the most economical tier, in keeping with a cost-conscious adapter.
ANTHROPIC_MODELS: dict[str, str] = {
    "opus": "claude-opus-4-8",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}
DEFAULT_ANTHROPIC_MODEL = ANTHROPIC_MODELS["haiku"]

# ILLUSTRATIVE, possibly-stale per-MTok prices, provided only as a labeled
# convenience for `--dry-run` demonstrations. They are NOT authoritative: the cost
# guard is only honest with current prices, so production callers must pass their
# own `Pricing` from https://www.anthropic.com/pricing rather than rely on these.
ILLUSTRATIVE_PRICING: dict[str, Pricing] = {
    "claude-opus-4-8": Pricing(input_usd_per_mtok=5.0, output_usd_per_mtok=25.0),
    "claude-sonnet-4-6": Pricing(input_usd_per_mtok=3.0, output_usd_per_mtok=15.0),
    "claude-haiku-4-5-20251001": Pricing(input_usd_per_mtok=1.0, output_usd_per_mtok=5.0),
}


class AnthropicLLMAdapter(LLMAdapter):
    """An opt-in Anthropic adapter. Disabled unless ``allow_network=True``.

    With ``allow_network=False`` (the default), :meth:`_invoke` raises
    :class:`LLMDisabledError` *before* the client is built or used, so constructing
    one is inert. ``pricing`` is **required** (no default) so the cost guard is never
    silently driven by stale numbers. A ``client`` may be injected (a fake in tests,
    or a pre-built ``anthropic.Anthropic``); otherwise the real client is imported
    lazily on first use.
    """

    name = "anthropic"
    provider = "anthropic"
    live = True

    def __init__(
        self,
        *,
        pricing: Pricing,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        api_key: str | None = None,
        allow_network: bool = False,
        max_cost_usd: float = 0.0,
        dry_run: bool = False,
        client: Any | None = None,
    ) -> None:
        self.pricing = pricing
        self.default_model = model
        self.api_key = api_key
        self.allow_network = allow_network
        self._client = client
        self.guard = CostGuard(self.pricing, max_cost_usd=max_cost_usd, dry_run=dry_run)

    def _build_client(self) -> Any:
        """Lazily construct the real ``anthropic.Anthropic`` client (opt-in only)."""
        try:
            import anthropic  # imported lazily; only on an opted-in, non-cached call
        except ImportError as exc:  # pragma: no cover - exercised only when opted in
            raise LLMError(
                "the Anthropic adapter needs the optional 'anthropic' package: "
                "pip install -e '.[llm]'"
            ) from exc
        return anthropic.Anthropic(api_key=self.api_key)

    def _invoke(self, request: LLMRequest, model: str) -> tuple[str, LLMUsage]:
        if not self.allow_network:
            raise LLMDisabledError(
                "the Anthropic adapter is disabled (offline-first default); construct "
                "it with allow_network=True and a current Pricing to opt in"
            )
        client = self._client or self._build_client()
        message = client.messages.create(
            model=model,
            max_tokens=request.max_output_tokens,
            temperature=request.temperature,
            system=request.system or "",
            messages=[{"role": "user", "content": request.prompt}],
        )
        text = "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", "text") == "text"
        )
        usage = LLMUsage(
            input_tokens=int(message.usage.input_tokens),
            output_tokens=int(message.usage.output_tokens),
        )
        return text, usage


def anthropic_adapter(
    *,
    pricing: Pricing,
    model: str = DEFAULT_ANTHROPIC_MODEL,
    allow_network: bool = False,
    **kwargs: Any,
) -> AnthropicLLMAdapter:
    """An opt-in Anthropic adapter (off by default; never used in tests).

    Disabled unless ``allow_network=True``. ``pricing`` is required. Provided to show
    the shape of a real adapter — the offline
    :class:`~bioscientist_os.llm.mock.MockLLMAdapter` is the one the project relies on.
    """
    return AnthropicLLMAdapter(
        pricing=pricing, model=model, allow_network=allow_network, **kwargs
    )


__all__ = [
    "ANTHROPIC_MODELS",
    "DEFAULT_ANTHROPIC_MODEL",
    "ILLUSTRATIVE_PRICING",
    "AnthropicLLMAdapter",
    "anthropic_adapter",
]
