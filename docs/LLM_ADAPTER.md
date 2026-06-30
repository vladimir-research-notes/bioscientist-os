# Optional LLM adapter (Milestone 10)

## TL;DR

`bioscientist-os` ships an **optional, disabled-by-default** LLM-adapter layer
(`src/bioscientist_os/llm/`). It is **not** part of the pipeline: the workbench's
default path and entire test suite run with **no language model at all**, on the
transparent non-LLM baselines (search, dictionary entity recognition, rule-based
claim extraction, the evidence table, the memo), which carry every correctness and
reproducibility guarantee. The LLM layer is a small, clearly-labeled option for
LLM-assisted experiments, built around three safeguards: a **cost guard**, a
**response cache**, and a **least-trusted provenance** stamp. The real (Anthropic)
adapter is off by default and never required for CI; a deterministic **mock**
adapter backs all tests.

## Why an adapter, not a feature

The methodological claim of this project is that evidence can be made *inspectable
without an opaque model in the loop*. An LLM is therefore deliberately kept at
arm's length: it is an adapter you can opt into for prototyping (e.g. comparing the
rule-based extraction's recall against an LLM's, or polishing a memo's prose), not
a step the default pipeline depends on. This mirrors the offline-first
[database-connector layer](DATABASES.md): one tiny interface, an honest provenance
stamp, a cache for determinism, and — unique to this layer — a cost guard.

```
LLMAdapter
  ├── MockLLMAdapter        deterministic, offline   -> data_source=fixture   [the test backend]
  ├── CachedLLMAdapter      read-through JSON cache   -> data_source=cache     (data/cache/llm/, gitignored)
  └── AnthropicLLMAdapter   opt-in, off by default    -> data_source=live      [opt-in, never in CI]
```

## The three safeguards

### 1. Cost guard (`--max-cost-usd`, dry-run)

Every call is **pre-priced** and refused *before any backend is touched* if it
would exceed the budget. `CostGuard.authorize` prices the call at the **worst
case** — `estimate_tokens(system + prompt)` input tokens plus the full
`max_output_tokens` as output — and raises `CostGuardError` if the running spend
would cross `max_cost_usd`. The default budget is **`0.0`**: out of the box,
nothing that costs money runs, and the free mock (zero pricing) is always
authorized. The actual spend recorded after a call uses the backend's *reported*
usage, not the worst-case estimate. `dry_run=True` returns the estimate without
ever calling out.

`estimate_tokens` is a transparent `ceil(len/4)` **estimate**, not a tokenizer; it
is used only to pre-price a call. A real backend's true token counts may differ —
that is expected, and billing uses the reported usage.

> **Pricing is required, never hardcoded.** A cost guard is only honest if its
> prices are current, and vendor prices drift. The real adapter therefore requires
> the caller to pass a `Pricing` explicitly (from the current vendor pricing page).
> `ILLUSTRATIVE_PRICING` is a clearly-labeled convenience for `--dry-run` demos and
> is **not** guaranteed current.

### 2. Response cache

`CachedLLMAdapter` wraps any adapter and persists each completion as canonical JSON
under `data/cache/llm/<provider>/<request_key>.json` (gitignored). The key is the
request's content hash (`LLMRequest.cache_key`), so it is keyed on everything that
affects the output (model, system, prompt, task, `max_output_tokens`,
`temperature`). A **cache hit** is stamped `data_source = cache`, costs **$0**, and
does not charge the cost guard's budget; a **cache miss** delegates to the inner
adapter (which prices and charges the call), then writes a copy. So a cached run of
an expensive model spends money exactly once, and repeated runs are deterministic
and offline.

### 3. Least-trusted provenance

Anything a language model produces enters the system at the **lowest** trust level.
`LLMResponse.epistemic_level` is always `unsupported_hypothesis`, and
`to_provenance()` stamps `extraction_method = llm:<adapter>:<model>`. Model output
**never** silently replaces a transparent baseline and is never promoted to
observed metadata, an extracted claim, or an inferred relation without a human or a
transparent method verifying it. See [SAFETY.md](SAFETY.md).

## The mock adapter (the test backend)

`MockLLMAdapter` is deterministic, offline, and free by default. The completion is
produced by an injected `responder` (default: `default_mock_responder`, which emits
a clearly-marked, content-derived, deterministic string that announces itself as a
mock). Determinism is what lets the whole adapter contract — cost guard, cache,
provenance — be exercised end-to-end with no paid API and no network. A non-zero
`Pricing` can be passed to *demonstrate* the cost guard offline.

## The opt-in Anthropic adapter

`AnthropicLLMAdapter` is the LLM analogue of the opt-in live connector. It is built
so **no network call can happen unless `allow_network=True`** *and* the client
actually performs I/O: with `allow_network=False` (the default), `_invoke` raises
`LLMDisabledError` before the client is built or used. The Anthropic client is an
injected dependency, so the parse / usage / provenance logic is exercised offline
with a fake client in tests; the real `anthropic.Anthropic` client is imported
**lazily** and only on an opted-in call. Model ids are the current Claude family
(`claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`); pass the one
you have access to. This adapter is best-effort and **never run in CI**.

## CLI

The `biosci llm` CLI uses the **mock adapter only**, deliberately — this keeps paid
calls and API keys out of the command line. The real adapter is used via the
library (`bioscientist_os.llm.AnthropicLLMAdapter`).

```bash
biosci llm info
biosci llm complete "Summarize senescence ↔ inflammation evidence." --task polish
biosci llm complete "expensive" --input-price 3 --output-price 15 \
    --max-output-tokens 4000 --max-cost-usd 0.0001        # refused by the cost guard
biosci llm complete "estimate" --input-price 3 --output-price 15 \
    --max-cost-usd 9 --dry-run                            # estimate, no call
biosci llm complete "cache me" --cache                    # 1st: fixture; 2nd: cache
```

`--input-price` / `--output-price` attach illustrative per-MTok pricing so the cost
guard is demonstrable offline. `scripts/08_llm_adapter_demo.py` runs the full
contract (free call, priced call, a refused over-budget call, a dry-run estimate,
and a cache round-trip) with no network.

## Limitations and non-claims

- This layer adds **no measured capability** to the workbench; it is infrastructure
  for *optional* experiments. No LLM extraction quality is claimed or measured here.
- The token estimate is a crude `len/4`; it is for pre-pricing only.
- `ILLUSTRATIVE_PRICING` may be stale — verify current vendor pricing before
  relying on a cost figure.
- The real adapter is never exercised in CI; only the mock/cache path carries the
  determinism guarantee.
- Model output is an **unsupported hypothesis**, never a clinical or biological
  claim (see [SAFETY.md](SAFETY.md)).
