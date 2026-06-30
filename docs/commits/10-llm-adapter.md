# Commit note: Milestone 10 — Add optional, cost-guarded LLM adapter interface

## Intent
Give the workbench an **optional** language-model layer for LLM-assisted experiments
without compromising any of its disciplines: keep the LLM **off the default path**
(the pipeline and the whole test suite use no model), make it **disabled by default**
and **mock-backed in tests**, guard every call with an explicit **cost budget**, and
ensure model output enters only as a **least-trusted unsupported hypothesis** that
never replaces a transparent baseline. Ship the interface + mock + cache + cost guard
plus one opt-in real adapter as a clearly-marked example (never run in CI).

## What the commit contains
- `src/bioscientist_os/llm/base.py`: `Pricing` / `LLMUsage` / `LLMRequest`
  (validated, stable `cache_key`) / `CostEstimate` / `LLMResponse` (provenance
  mapping + `to_provenance()` at level `unsupported_hypothesis`), `estimate_tokens`
  (transparent `len/4`), `CostGuard` (worst-case pre-authorization that raises
  `CostGuardError` before any backend call; actual-spend accumulation; dry-run), and
  the `LLMAdapter` ABC whose `generate()` enforces guard + dry-run + provenance.
- `src/bioscientist_os/llm/mock.py`: `MockLLMAdapter` — deterministic, offline,
  free by default, injectable `responder`; the backend used in **all** tests.
- `src/bioscientist_os/llm/cache.py`: `CachedLLMAdapter` — read-through JSON cache
  under `data/cache/llm/` (gitignored); a hit is `cache`, costs `$0`, charges no
  budget; a miss delegates and writes a canonical copy; offline-first.
- `src/bioscientist_os/llm/anthropic_adapter.py`: opt-in `AnthropicLLMAdapter` (off
  by default; raises `LLMDisabledError` before any client use), **required explicit
  pricing**, injectable/lazy client, current Claude model ids, labeled
  `ILLUSTRATIVE_PRICING`. Never exercised in CI.
- `src/bioscientist_os/llm/__init__.py`: the public surface.
- `src/bioscientist_os/cli.py`: a `biosci llm` group (`info`, `complete`) using the
  **mock adapter only** (no paid calls / API keys on the CLI), with `--max-cost-usd`,
  `--dry-run`, `--cache`, and illustrative `--input-price`/`--output-price`; `info`
  and the module docstring → Milestones 0–10.
- `scripts/08_llm_adapter_demo.py`: an install-free, offline demo of the full
  contract.
- `tests/test_llm.py` (31): the value objects, the guard (incl. **over-budget refusal
  before any invoke**), the mock (determinism/usage/cost/provenance), the dry-run, the
  cache (miss/hit/free-hit/canonical/offline), the opt-in Anthropic adapter
  (disabled-by-default + injected-client parse), and the `biosci llm` CLI. 274 total,
  1 skipped without `matplotlib`.
- Docs + website: `docs/LLM_ADAPTER.md`, `docs/milestones/10-llm-adapter.md`,
  `docs/commits/10-llm-adapter.md`, `docs/review_notes/10-llm-adapter-human-review.md`;
  `SAFETY.md` (LLM section), `RESULTS.md` (status row + section, test count → 274),
  `REPRODUCIBILITY.md` (the demo step + `biosci llm` examples), `ARCHITECTURE.md`
  (the `llm/` layer); `site/llm.html` (new), the nav link added across all pages, and
  `milestones`/`results`/`index` updated to M10 → Done and 274 tests.

## Why it is safe to commit
CPU-only, offline, no network or paid API, no GPU. The LLM layer is **off the default
path** and the test suite uses only the deterministic mock — no test opens a socket or
needs the optional `anthropic` package (imported lazily, only on an opted-in call).
The cost guard defaults to `$0`, so nothing that costs money runs out of the box, and
an over-budget call is refused before any backend is touched (a test pins the spy's
invoke count at 0). The real adapter is disabled unless `allow_network=True` and is
never run in CI. The only writable artifact is the gitignored `data/cache/llm/`
(canonical, regenerable); nothing under it is staged. No secrets, caches, virtualenvs,
weights, or large data are staged. Model output is framed throughout as an
**unsupported hypothesis** and never as a clinical or biological claim
(see `docs/SAFETY.md`). `ruff check` is clean on the new/changed files; the working
tree is clean after commit.
