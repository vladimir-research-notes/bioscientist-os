# Human review: Milestone 10 — Optional, cost-guarded LLM adapter interface

## TL;DR
A new optional `llm/` subpackage and `biosci llm` command add a language-model
adapter layer that is **off the default path**: the pipeline and the whole test suite
still run with no model. It mirrors the connector layer — one adapter interface, a
response cache, an honest provenance stamp — plus a **cost guard** that pre-prices
every call and refuses, before any backend is touched, anything over `--max-cost-usd`
(default `0.0`). A deterministic **mock** adapter backs all tests; an opt-in Anthropic
adapter ships as a clearly-marked, off-by-default example never run in CI. Model
output enters only as an **unsupported hypothesis**. 31 new tests; 274 passed, 1
skipped (offline).

## What changed
- `src/bioscientist_os/llm/base.py` — `Pricing`/`LLMUsage`/`LLMRequest`/`CostEstimate`/
  `LLMResponse`, `estimate_tokens`, `CostGuard`, and the `LLMAdapter` ABC.
- `src/bioscientist_os/llm/mock.py` — `MockLLMAdapter` (deterministic, offline, the
  test backend) + `default_mock_responder`.
- `src/bioscientist_os/llm/cache.py` — `CachedLLMAdapter` (read-through JSON cache
  under `data/cache/llm/`, gitignored).
- `src/bioscientist_os/llm/anthropic_adapter.py` — opt-in `AnthropicLLMAdapter` (off
  by default, required explicit pricing, injectable/lazy client) + `ILLUSTRATIVE_PRICING`.
- `src/bioscientist_os/llm/__init__.py` — the public surface.
- `src/bioscientist_os/cli.py` — the `biosci llm` group (`info`, `complete`),
  mock-only; `info` + docstring → M0–10.
- `scripts/08_llm_adapter_demo.py` — offline demo of the full contract.
- `tests/test_llm.py` — 31 tests.
- Docs/website: `docs/LLM_ADAPTER.md`, this note, the milestone and commit notes,
  `SAFETY.md`, `RESULTS.md`, `REPRODUCIBILITY.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
  and `site/` (new `llm.html`, nav link on every page, `milestones`/`results`/`index`
  → M10 Done and 274 tests).

## Commands run
```bash
python3 -m pytest -q                                   # 274 passed, 1 skipped (offline)
python3 scripts/08_llm_adapter_demo.py                 # full contract, offline, no API
ruff check src/bioscientist_os/llm src/bioscientist_os/cli.py \
    scripts/08_llm_adapter_demo.py tests/test_llm.py   # clean
biosci llm info
biosci llm complete "Summarize senescence ↔ inflammation evidence." --task polish
```

## Test status
274 passed, 1 skipped (the figure-rendering test, skipped because `matplotlib` is not
installed). `ruff check` clean on the new/changed files. All tests offline; no network,
paid API, or GPU, and the optional `anthropic` package is not required.

## Known limitations
- This layer adds **no measured capability**. It is infrastructure for *optional*
  experiments; no LLM extraction quality is claimed or measured here.
- `estimate_tokens` is a crude `len/4`, used only to pre-price a call; a real backend's
  true token counts will differ (billing uses the reported usage).
- `ILLUSTRATIVE_PRICING` may be stale; the real adapter requires the caller to pass
  current pricing, so the project hardcodes no vendor price list that could drift.
- The real (Anthropic) adapter is never exercised in CI; only the mock/cache path
  carries the determinism guarantee.

## Possible misleading artifacts
- A reader could assume the workbench now "uses an LLM". It does **not** by default —
  the pipeline and tests use no model. The CLI, `info`, and docs all state this; a
  reviewer should confirm the framing is unmistakable.
- The mock output is a deterministic, clearly-marked string ("[MOCK LLM OUTPUT …]"),
  not a real model answer; it should never be cited as model reasoning.
- The cost figures from the CLI use illustrative `--input-price`/`--output-price` (or
  `ILLUSTRATIVE_PRICING`); they demonstrate the guard, they are not real billing.
- Model output is stamped `unsupported_hypothesis`; it must not be read as a clinical
  or biological claim.

## Human feedback
<!-- Human will fill this later. -->
