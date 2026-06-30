"""Optional, cost-guarded LLM adapter layer (Milestone 10) — OFF the default path.

This subpackage is the project's **optional** language-model layer. It is not part
of the pipeline: the workbench's default path and entire test suite run with no
language model at all, on the transparent, non-LLM baselines (search, dictionary
entity recognition, rule-based claim extraction, the evidence table, the memo),
which carry every correctness and reproducibility guarantee. The LLM layer is a
small, clearly-labeled option for LLM-assisted experiments (e.g. claim-extraction
or memo-polish prototypes) that mirrors the offline-first connector layer::

    LLMAdapter
      ├── MockLLMAdapter        deterministic, offline   -> data_source=fixture   [test backend]
      ├── CachedLLMAdapter      read-through JSON cache   -> data_source=cache     [data/cache/llm/]
      └── AnthropicLLMAdapter   opt-in HTTP, off default  -> data_source=live      [off by default]

Three disciplines, inherited from the rest of the package:

* **Cost guard.** Every call is pre-priced and refused before any backend is
  touched if it would exceed ``max_cost_usd`` (default ``0.0`` — nothing that costs
  money runs out of the box); ``dry_run`` estimates without calling out. A real
  adapter requires the caller to pass **current** :class:`Pricing` explicitly — the
  project hardcodes no vendor price list that could silently drift.
* **Disabled by default, mock in tests.** The real adapter raises before any
  network call unless explicitly opted in; the mock backs all tests offline.
* **Least-trusted provenance.** Model output enters the system as an *unsupported
  hypothesis* stamped ``llm:<adapter>``; it never replaces a transparent baseline
  and is never silently promoted (see ``docs/SAFETY.md`` and ``docs/LLM_ADAPTER.md``).
"""

from __future__ import annotations

from bioscientist_os.llm.anthropic_adapter import (
    ANTHROPIC_MODELS,
    DEFAULT_ANTHROPIC_MODEL,
    ILLUSTRATIVE_PRICING,
    AnthropicLLMAdapter,
    anthropic_adapter,
)
from bioscientist_os.llm.base import (
    LLM_EPISTEMIC_LEVEL,
    CostEstimate,
    CostGuard,
    CostGuardError,
    LLMAdapter,
    LLMDisabledError,
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    Pricing,
    estimate_tokens,
)
from bioscientist_os.llm.cache import CachedLLMAdapter
from bioscientist_os.llm.mock import (
    MOCK_MODEL,
    MockLLMAdapter,
    Responder,
    default_mock_responder,
)

__all__ = [
    # base
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
    # mock (the test backend)
    "Responder",
    "MOCK_MODEL",
    "default_mock_responder",
    "MockLLMAdapter",
    # cache
    "CachedLLMAdapter",
    # anthropic (opt-in)
    "ANTHROPIC_MODELS",
    "DEFAULT_ANTHROPIC_MODEL",
    "ILLUSTRATIVE_PRICING",
    "AnthropicLLMAdapter",
    "anthropic_adapter",
]
