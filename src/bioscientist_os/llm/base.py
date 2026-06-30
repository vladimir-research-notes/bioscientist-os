"""LLM-adapter foundations: the interface, request/response types, and cost guard.

This module is the optional, **disabled-by-default** contract every LLM adapter
implements (Milestone 10). The workbench's default and test paths never call a
language model — the transparent, non-LLM baselines (search, dictionary entity
recognition, rule-based claim extraction, the evidence table, the memo) carry the
project's correctness and reproducibility guarantees. The LLM layer is a small,
clearly-labeled *option* that mirrors the offline-first database-connector layer
(:mod:`bioscientist_os.databases.base`): one tiny interface, an honest provenance
stamp on every response, a cache for determinism, and — unique to this layer — a
**cost guard** that refuses to spend money you did not authorize.

Four pieces live here, all dependency-light (stdlib + the schemas):

* the value objects — :class:`Pricing`, :class:`LLMUsage`, :class:`LLMRequest`,
  :class:`CostEstimate`, :class:`LLMResponse` — frozen, JSON-friendly, and
  deterministic (a request hashes to a stable :meth:`LLMRequest.cache_key`);
* :func:`estimate_tokens` — a transparent, clearly-labeled ``len/4`` token
  *estimate* (not a real tokenizer), used only to pre-price a call before it runs;
* :class:`CostGuard` — pre-authorizes a call against ``max_cost_usd`` using the
  conservative worst-case output, raises :class:`CostGuardError` *before* any
  backend is touched if it would exceed the budget, and accumulates the actual
  spend afterwards. ``dry_run`` returns the estimate without ever calling out;
* :class:`LLMAdapter` — the abstract adapter. Subclasses implement one method
  (:meth:`LLMAdapter._invoke`); the base enforces the guard, the dry-run, and the
  provenance stamp uniformly. Concrete adapters are
  :class:`~bioscientist_os.llm.mock.MockLLMAdapter` (used in **all** tests),
  :class:`~bioscientist_os.llm.cache.CachedLLMAdapter`, and the opt-in
  :class:`~bioscientist_os.llm.anthropic_adapter.AnthropicLLMAdapter`.

**Epistemic stance (hard rule).** Anything a language model produces enters the
system at the *lowest* trust level: :attr:`LLMResponse.epistemic_level` is
:attr:`~bioscientist_os.schemas.EpistemicLevel.unsupported_hypothesis`, and
:meth:`LLMResponse.to_provenance` stamps it ``llm:<adapter>``. Model output never
silently replaces a transparent baseline and is never promoted to observed
metadata, an extracted claim, or an inferred relation without a human or a
transparent method verifying it (see ``docs/SAFETY.md``).
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from bioscientist_os.schemas import DataSource, EpistemicLevel, Provenance

# Anything a language model says enters the workbench as the least-trusted level.
# A transparent method or a human must verify it before it is anything more.
LLM_EPISTEMIC_LEVEL = EpistemicLevel.unsupported_hypothesis

# Float tolerance for the budget comparison, so exact-equality budgets (e.g. a
# zero-priced mock call under ``max_cost_usd=0.0``) are authorized, not rejected.
_EPS = 1e-9

# Rounding applied only in JSON output (mirrors the rest of the package).
_NDIGITS = 6


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(RuntimeError):
    """Base class for adapter failures (distinct from a budget refusal)."""


class CostGuardError(LLMError):
    """Raised by :meth:`CostGuard.authorize` when a call would exceed the budget.

    Raised *before* any backend is contacted, so a refused call costs nothing and
    performs no I/O. Carries the estimate and the budget for an honest message.
    """

    def __init__(self, estimate: CostEstimate, *, spent_usd: float, max_cost_usd: float) -> None:
        self.estimate = estimate
        self.spent_usd = spent_usd
        self.max_cost_usd = max_cost_usd
        super().__init__(
            f"cost guard: estimated ${estimate.usd:.6f} for this call would bring spend "
            f"to ${spent_usd + estimate.usd:.6f}, over the ${max_cost_usd:.6f} budget "
            "(raise --max-cost-usd to authorize, or use --dry-run to estimate only)"
        )


class LLMDisabledError(LLMError):
    """Raised when a live adapter is used without opting in (``allow_network=False``).

    The offline-first default: a real adapter raises this *before* importing its
    client or performing any network call, so simply constructing one is inert.
    """


# ---------------------------------------------------------------------------
# Token estimate (transparent, not a real tokenizer)
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """A transparent ``ceil(len/4)`` **estimate** of the tokens in ``text``.

    Deliberately crude and provider-agnostic: it exists only to *pre-price* a call
    for the cost guard before the call runs, where a rough upper-ish bound is
    enough. It is **not** a tokenizer and is never used to bill — the actual spend
    is recorded from the backend's reported usage (see :meth:`LLMAdapter.generate`).
    A real adapter may report different true token counts; that is expected and
    documented.
    """
    if not text:
        return 0
    return math.ceil(len(text) / 4)


# ---------------------------------------------------------------------------
# Pricing and usage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pricing:
    """Per-token price, in USD per **million** tokens (the common vendor unit).

    The cost guard is honest only if its prices are current, so the project does
    **not** hardcode a vendor price list anywhere it could silently drift: a real
    adapter requires the caller to pass current pricing explicitly. The mock
    adapter is free (:meth:`zero`).
    """

    input_usd_per_mtok: float = 0.0
    output_usd_per_mtok: float = 0.0

    @classmethod
    def zero(cls) -> Pricing:
        """Free pricing — the mock adapter's default (offline, costs nothing)."""
        return cls(0.0, 0.0)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """USD cost of ``input_tokens`` prompt + ``output_tokens`` completion tokens."""
        return (
            input_tokens / 1_000_000 * self.input_usd_per_mtok
            + output_tokens / 1_000_000 * self.output_usd_per_mtok
        )

    def to_dict(self) -> dict:
        return {
            "input_usd_per_mtok": self.input_usd_per_mtok,
            "output_usd_per_mtok": self.output_usd_per_mtok,
        }


@dataclass(frozen=True)
class LLMUsage:
    """Token usage for one call. ``estimated`` is True for a dry-run (no real call)."""

    input_tokens: int
    output_tokens: int
    estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated": self.estimated,
        }


# ---------------------------------------------------------------------------
# Request / estimate / response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMRequest:
    """One completion request — the unit the cost guard prices and the cache keys.

    ``model`` is optional here; the adapter resolves ``None`` to its default model.
    ``task`` is a free-form label (e.g. ``"polish"`` / ``"extract"``) recorded for
    provenance and folded into the cache key. The request is frozen and hashes to a
    stable :meth:`cache_key`, so identical requests are deduplicated by the cache.
    """

    prompt: str
    system: str = ""
    model: str | None = None
    max_output_tokens: int = 512
    temperature: float = 0.0
    task: str | None = None

    def __post_init__(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise ValueError("LLMRequest.prompt must be a non-empty string")
        if self.max_output_tokens < 1:
            raise ValueError("LLMRequest.max_output_tokens must be >= 1")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("LLMRequest.temperature must be in [0, 2]")

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "system": self.system,
            "model": self.model,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "task": self.task,
        }

    def cache_key(self) -> str:
        """A stable sha256 over the request content (canonical, sorted-key JSON).

        Two requests with the same content (including ``model``, ``system``,
        ``task``, ``max_output_tokens``, ``temperature``) share a key and so a cache
        entry; any change yields a different key. Independent of process or run.
        """
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CostEstimate:
    """A pre-call price estimate (worst-case output = ``max_output_tokens``)."""

    input_tokens: int
    output_tokens: int
    usd: float

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": round(self.usd, _NDIGITS),
        }


@dataclass(frozen=True)
class LLMResponse:
    """The result of one (possibly cached or dry-run) completion, with provenance.

    ``provider`` is the adapter family (``"mock"`` / ``"anthropic"``);
    ``served_from_cache`` and ``dry_run`` say *how* this particular response was
    produced. ``cost_usd`` is the **marginal** USD spent on this call — zero for a
    cache hit (the bytes came from a local file) and zero for a dry-run (nothing was
    sent). The four-level discipline is baked in: :attr:`epistemic_level` is always
    ``unsupported_hypothesis`` and :meth:`to_provenance` stamps ``llm:<adapter>``.
    """

    text: str
    model: str
    usage: LLMUsage
    cost_usd: float
    adapter: str
    provider: str
    live: bool
    request_key: str
    served_from_cache: bool = False
    dry_run: bool = False
    epistemic_level: EpistemicLevel = LLM_EPISTEMIC_LEVEL

    @property
    def data_source(self) -> DataSource:
        """Where these bytes came from, mapped onto the project's provenance enum.

        A cache hit is ``cache``; a real network call is ``live``; the deterministic
        offline mock is ``fixture`` (a committed, reproducible, offline source — the
        same status a fixture record carries).
        """
        if self.served_from_cache:
            return DataSource.cache
        if self.live:
            return DataSource.live
        return DataSource.fixture

    def to_provenance(
        self, *, paper_id: str | None = None, source_snippet: str | None = None
    ) -> Provenance:
        """A :class:`~bioscientist_os.schemas.Provenance` stamp for this output.

        ``extraction_method`` is ``llm:<adapter>:<model>`` and
        ``epistemic_level`` is ``unsupported_hypothesis`` — so any model output that
        is carried downstream is unmistakably model-generated and least-trusted,
        never silently promoted to a transparent-baseline level (see SAFETY.md).
        """
        return Provenance(
            paper_id=paper_id,
            source_snippet=source_snippet,
            extraction_method=f"llm:{self.adapter}:{self.model}",
            data_source=self.data_source,
            epistemic_level=self.epistemic_level,
        )

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "model": self.model,
            "adapter": self.adapter,
            "provider": self.provider,
            "live": self.live,
            "served_from_cache": self.served_from_cache,
            "dry_run": self.dry_run,
            "data_source": self.data_source.value,
            "epistemic_level": self.epistemic_level.value,
            "extraction_method": f"llm:{self.adapter}:{self.model}",
            "usage": self.usage.to_dict(),
            "cost_usd": round(self.cost_usd, _NDIGITS),
            "request_key": self.request_key,
        }


# ---------------------------------------------------------------------------
# Cost guard
# ---------------------------------------------------------------------------


@dataclass
class CostGuard:
    """Pre-authorize calls against a USD budget; accumulate the actual spend.

    Authorization is **conservative**: it prices the call at the worst case
    (``max_output_tokens`` output tokens) using :func:`estimate_tokens`, and raises
    :class:`CostGuardError` *before* any backend is touched if that would push the
    running spend over ``max_cost_usd``. The default budget is ``0.0`` — the safe
    default: out of the box nothing that costs money runs, and the free mock (zero
    pricing) is always authorized. ``dry_run`` makes :meth:`LLMAdapter.generate`
    return the estimate without ever calling out.
    """

    pricing: Pricing
    max_cost_usd: float = 0.0
    dry_run: bool = False
    spent_usd: float = field(default=0.0)

    def estimate(self, request: LLMRequest) -> CostEstimate:
        """Worst-case price of ``request`` (output billed at ``max_output_tokens``)."""
        input_tokens = estimate_tokens(request.system) + estimate_tokens(request.prompt)
        output_tokens = request.max_output_tokens
        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usd=self.pricing.cost(input_tokens, output_tokens),
        )

    def authorize(self, request: LLMRequest) -> CostEstimate:
        """Return the estimate, or raise :class:`CostGuardError` if over budget."""
        est = self.estimate(request)
        if self.spent_usd + est.usd > self.max_cost_usd + _EPS:
            raise CostGuardError(
                est, spent_usd=self.spent_usd, max_cost_usd=self.max_cost_usd
            )
        return est

    def record(self, usd: float) -> None:
        """Accumulate the *actual* spend of a completed call."""
        self.spent_usd += usd

    def remaining(self) -> float:
        """USD budget left (may be negative only via rounding; never charged past)."""
        return self.max_cost_usd - self.spent_usd


# ---------------------------------------------------------------------------
# Adapter base
# ---------------------------------------------------------------------------


class LLMAdapter(ABC):
    """Abstract LLM adapter: guard a call, run it, stamp its provenance.

    Subclasses set ``name`` (e.g. ``"mock"``), ``provider`` (the family),
    ``default_model``, ``live`` (whether ``_invoke`` performs real network I/O),
    ``pricing``, and ``guard``; and implement exactly one method, :meth:`_invoke`,
    returning the completion text and the backend's reported token usage. The base
    :meth:`generate` enforces the cost guard and the dry-run, charges the actual
    spend, and builds the provenance-stamped :class:`LLMResponse` uniformly.
    """

    name: str
    provider: str
    default_model: str
    live: bool
    pricing: Pricing
    guard: CostGuard

    @abstractmethod
    def _invoke(self, request: LLMRequest, model: str) -> tuple[str, LLMUsage]:
        """Run the completion for ``request`` against ``model``; return (text, usage)."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Cost-guard, run (unless ``dry_run``), charge, and stamp one completion.

        Order matters for safety: the guard is consulted **first** and raises before
        any backend is touched. On a dry-run, no backend is called and ``cost_usd``
        is the estimate (no spend is recorded). Otherwise the call runs, the actual
        usage is priced and added to the running spend, and the response carries this
        adapter's honest ``provider`` / ``live`` provenance.
        """
        model = request.model or self.default_model
        estimate = self.guard.authorize(request)

        if self.guard.dry_run:
            return LLMResponse(
                text="",
                model=model,
                usage=LLMUsage(estimate.input_tokens, estimate.output_tokens, estimated=True),
                cost_usd=estimate.usd,
                adapter=self.name,
                provider=self.provider,
                live=self.live,
                request_key=request.cache_key(),
                served_from_cache=False,
                dry_run=True,
            )

        text, usage = self._invoke(request, model)
        cost = self.pricing.cost(usage.input_tokens, usage.output_tokens)
        self.guard.record(cost)
        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cost_usd=cost,
            adapter=self.name,
            provider=self.provider,
            live=self.live,
            request_key=request.cache_key(),
            served_from_cache=False,
            dry_run=False,
        )

    def complete(self, prompt: str, **kwargs: object) -> LLMResponse:
        """Convenience: build an :class:`LLMRequest` from ``prompt`` and generate."""
        return self.generate(LLMRequest(prompt=prompt, **kwargs))  # type: ignore[arg-type]

    def describe(self) -> dict[str, object]:
        """A small, inspectable summary of the adapter for the CLI and tests."""
        return {
            "name": self.name,
            "provider": self.provider,
            "default_model": self.default_model,
            "live": self.live,
            "pricing": self.pricing.to_dict(),
            "max_cost_usd": self.guard.max_cost_usd,
            "dry_run": self.guard.dry_run,
            "spent_usd": round(self.guard.spent_usd, _NDIGITS),
        }


__all__ = [
    "LLM_EPISTEMIC_LEVEL",
    "LLMError",
    "CostGuardError",
    "LLMDisabledError",
    "estimate_tokens",
    "Pricing",
    "LLMUsage",
    "LLMRequest",
    "CostEstimate",
    "LLMResponse",
    "CostGuard",
    "LLMAdapter",
]
