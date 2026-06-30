#!/usr/bin/env python3
"""Demonstrate the optional, cost-guarded LLM adapter, fully offline (Milestone 10).

A thin, install-free smoke for :mod:`bioscientist_os.llm`. It exercises the whole
adapter contract **without any network call, paid API, or API key**, using the
deterministic mock adapter:

1. a free mock completion (zero pricing) with its provenance stamp;
2. a *priced* mock completion under a budget, showing the recorded spend;
3. the cost guard **refusing** a call that would exceed ``--max-cost-usd``;
4. a ``--dry-run``-style estimate that makes no call;
5. a cache round-trip (miss then a free, offline cache hit) in a temp directory.

Everything is deterministic, so re-running prints the same signatures. No artifacts
are committed; the temp cache is discarded on exit.

    python3 scripts/08_llm_adapter_demo.py

Reminder: the workbench pipeline uses NO language model. This layer is optional and
model output is an UNSUPPORTED HYPOTHESIS, never a transparent-baseline result
(see docs/SAFETY.md and docs/LLM_ADAPTER.md).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make the src/ layout importable without requiring `pip install -e .`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bioscientist_os.llm import (  # noqa: E402
    CachedLLMAdapter,
    CostGuardError,
    LLMRequest,
    MockLLMAdapter,
    Pricing,
)

_PROMPT = "Summarize the evidence linking cellular senescence to chronic inflammation."


def main() -> int:
    print("bioscientist-os — optional LLM adapter demo (offline, no API, no key)\n")

    # 1) free mock completion ------------------------------------------------
    free = MockLLMAdapter()
    r1 = free.generate(LLMRequest(prompt=_PROMPT, task="polish"))
    prov = r1.to_provenance()
    print("1) free mock completion")
    print(f"     cost=${r1.cost_usd:.6f}  data_source={r1.data_source.value}  "
          f"level={prov.epistemic_level.value}  method={prov.extraction_method}")
    print(f"     usage: input={r1.usage.input_tokens} output={r1.usage.output_tokens}")

    # 2) priced mock completion under budget --------------------------------
    priced = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=1.0)
    r2 = priced.generate(LLMRequest(prompt=_PROMPT, task="polish"))
    print("\n2) priced mock completion (illustrative $3/$15 per MTok, budget $1.00)")
    print(f"     cost=${r2.cost_usd:.6f}  spent=${priced.guard.spent_usd:.6f}  "
          f"remaining=${priced.guard.remaining():.6f}")

    # 3) cost guard refuses an over-budget call -----------------------------
    tight = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=0.0001)
    print("\n3) cost guard refuses a call over a $0.0001 budget")
    try:
        tight.generate(LLMRequest(prompt="x" * 8000, max_output_tokens=4000))
        print("     ERROR: the guard did not fire")
        return 1
    except CostGuardError as exc:
        print(f"     refused (no backend touched, $0 spent): {exc}")

    # 4) dry-run estimate, no call ------------------------------------------
    estimator = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=10.0, dry_run=True)
    r4 = estimator.generate(LLMRequest(prompt=_PROMPT, max_output_tokens=1000))
    print("\n4) --dry-run estimate (no call made)")
    print(f"     estimated cost=${r4.cost_usd:.6f}  estimated={r4.usage.estimated}  "
          f"spent=${estimator.guard.spent_usd:.6f}")

    # 5) cache round-trip ----------------------------------------------------
    print("\n5) cache round-trip (miss → free offline hit)")
    with tempfile.TemporaryDirectory() as td:
        inner = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=1.0)
        cached = CachedLLMAdapter(inner, td)
        req = LLMRequest(prompt=_PROMPT, task="polish")
        miss = cached.generate(req)
        hit = cached.generate(req)
        print(f"     miss: cost=${miss.cost_usd:.6f} served_from_cache={miss.served_from_cache} "
              f"data_source={miss.data_source.value}")
        print(f"     hit : cost=${hit.cost_usd:.6f} served_from_cache={hit.served_from_cache} "
              f"data_source={hit.data_source.value}  (spent unchanged: "
              f"${inner.guard.spent_usd:.6f})")

    print("\nDone. The workbench pipeline uses no language model; this layer is optional,")
    print("disabled by default for real backends, and its output is an unsupported")
    print("hypothesis, never a transparent-baseline result (see docs/SAFETY.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
