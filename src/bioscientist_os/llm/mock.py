"""The mock LLM adapter — deterministic, offline, used in **all** tests (Milestone 10).

The mock is the adapter the project's default path and entire test suite use. It
performs **no** network I/O, costs nothing (its default :class:`Pricing` is
:meth:`~bioscientist_os.llm.base.Pricing.zero`), and is fully deterministic: the
same :class:`~bioscientist_os.llm.base.LLMRequest` always yields byte-identical
output. That determinism is what lets the LLM layer be exercised end-to-end —
cost guard, cache, provenance — without a paid API or a flaky network.

The completion text is produced by a ``responder`` callable, injected exactly like
the live database connector's transport, so tests can drive any behavior they need
offline. The default responder (:func:`default_mock_responder`) emits a clearly
marked, content-derived, deterministic string — it announces itself as a mock and
is never mistaken for a real model's output.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from bioscientist_os.llm.base import (
    CostGuard,
    LLMAdapter,
    LLMRequest,
    LLMUsage,
    Pricing,
    estimate_tokens,
)

# A responder turns a request (and the resolved model) into completion text.
Responder = Callable[[LLMRequest, str], str]

# The mock's default model id — deliberately not a real model name.
MOCK_MODEL = "mock-llm-1"


def default_mock_responder(request: LLMRequest, model: str) -> str:
    """A deterministic, offline, clearly-marked mock completion.

    The output announces itself as a mock, echoes the first line of the prompt, and
    ends with a stable signature (a short hash of the system+prompt) so a test can
    pin determinism. It is content-derived and reproducible, but it is **not** a
    summary, an extraction, or anything to be trusted as model reasoning.
    """
    first_line = next((ln.strip() for ln in request.prompt.splitlines() if ln.strip()), "")
    signature = hashlib.sha256(
        (request.system + "\x00" + request.prompt + "\x00" + model).encode("utf-8")
    ).hexdigest()[:12]
    return (
        "[MOCK LLM OUTPUT — deterministic, offline, not a real model]\n"
        f"task={request.task or 'complete'} model={model}\n"
        f"echo: {first_line[:200]}\n"
        f"signature: {signature}"
    )


class MockLLMAdapter(LLMAdapter):
    """A deterministic, offline LLM adapter (free by default; the test backend).

    Construct with an optional ``responder`` (default: :func:`default_mock_responder`)
    and an optional non-zero ``pricing`` to *demonstrate* the cost guard without any
    real API. ``max_cost_usd`` / ``dry_run`` configure the shared
    :class:`~bioscientist_os.llm.base.CostGuard`. Reported usage is the
    :func:`~bioscientist_os.llm.base.estimate_tokens` count of the input and of the
    produced text — so a non-zero ``pricing`` yields a real, reproducible cost.
    """

    name = "mock"
    provider = "mock"
    live = False

    def __init__(
        self,
        *,
        responder: Responder = default_mock_responder,
        pricing: Pricing | None = None,
        max_cost_usd: float = 0.0,
        dry_run: bool = False,
        default_model: str = MOCK_MODEL,
    ) -> None:
        self._responder = responder
        self.pricing = pricing if pricing is not None else Pricing.zero()
        self.default_model = default_model
        self.guard = CostGuard(self.pricing, max_cost_usd=max_cost_usd, dry_run=dry_run)

    def _invoke(self, request: LLMRequest, model: str) -> tuple[str, LLMUsage]:
        text = self._responder(request, model)
        usage = LLMUsage(
            input_tokens=estimate_tokens(request.system) + estimate_tokens(request.prompt),
            output_tokens=estimate_tokens(text),
        )
        return text, usage


__all__ = ["Responder", "MOCK_MODEL", "default_mock_responder", "MockLLMAdapter"]
