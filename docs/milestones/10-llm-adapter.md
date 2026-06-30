# Milestone 10 — Optional, cost-guarded LLM adapter interface

## Summary

The workbench gains an **optional, disabled-by-default** language-model layer
(`src/bioscientist_os/llm/`) that is deliberately kept *off* the pipeline: the
default path and the entire test suite still run with **no language model**, on the
transparent non-LLM baselines that carry every correctness and reproducibility
guarantee. The layer mirrors the offline-first database-connector layer — one tiny
adapter interface, an honest provenance stamp, a response cache for determinism —
plus the safeguard unique to spending money: a **cost guard** that pre-prices every
call and refuses, before any backend is touched, anything over `--max-cost-usd`
(default `0.0`). A deterministic **mock** adapter backs all tests; an opt-in
Anthropic adapter ships as a clearly-marked example that is off by default and
never run in CI. Model output enters the system as an *unsupported hypothesis* and
never replaces a transparent baseline.

## Deliverables

- **`src/bioscientist_os/llm/base.py`** — the foundations:
  - value objects `Pricing`, `LLMUsage`, `LLMRequest` (frozen, validated, hashing to
    a stable `cache_key`), `CostEstimate`, `LLMResponse` (carries `provider`/`live`,
    `served_from_cache`/`dry_run`, a `data_source` property mapping to the project's
    provenance enum, and `to_provenance()` stamping `llm:<adapter>` at level
    `unsupported_hypothesis`);
  - `estimate_tokens` — a transparent `ceil(len/4)` estimate used only to pre-price;
  - `CostGuard` — worst-case pre-authorization (raises `CostGuardError` before any
    backend call), actual-spend accumulation, and a dry-run mode;
  - `LLMAdapter` — the ABC whose `generate()` enforces guard + dry-run + provenance
    uniformly; subclasses implement only `_invoke`.
- **`src/bioscientist_os/llm/mock.py`** — `MockLLMAdapter`, the deterministic,
  offline, free-by-default backend used in **all** tests, with an injectable
  `responder` (default `default_mock_responder`, a clearly-marked deterministic
  string) and an optional non-zero `Pricing` to *demonstrate* the guard.
- **`src/bioscientist_os/llm/cache.py`** — `CachedLLMAdapter`, a read-through JSON
  cache under `data/cache/llm/` (gitignored): a hit is `data_source=cache`, costs
  `$0`, and charges no budget; a miss delegates and writes a copy. Canonical on
  disk, offline-first, shares the inner adapter's guard.
- **`src/bioscientist_os/llm/anthropic_adapter.py`** — the opt-in `AnthropicLLMAdapter`
  (off by default; raises `LLMDisabledError` before any client use), with **required
  explicit pricing**, an injectable client (so the parse path is exercised offline),
  lazy `anthropic` import, the current Claude model ids, and a clearly-labeled
  `ILLUSTRATIVE_PRICING` convenience.
- **CLI** (`cli.py`): a `biosci llm` group — `llm info` (describe the layer + its
  safeguards) and `llm complete` (`--system`, `--task`, `--model`,
  `--max-output-tokens`, `--temperature`, `--max-cost-usd`, `--input-price`,
  `--output-price`, `--dry-run`, `--cache`, `--cache-dir`, `--json`). The CLI uses
  the **mock adapter only**, keeping paid calls and API keys off the command line.
  The module docstring and `info` status are updated to Milestones 0–10.
- **`scripts/08_llm_adapter_demo.py`** — an install-free, offline demo of the full
  contract (free call, priced call, a refused over-budget call, a dry-run estimate,
  a cache round-trip). No network, no artifacts committed.
- **Docs/website**: new `docs/LLM_ADAPTER.md`; `docs/SAFETY.md` gains an LLM section;
  `RESULTS.md` / `REPRODUCIBILITY.md` / `ARCHITECTURE.md` / `ROADMAP.md` updated; new
  `site/llm.html`, the nav link added across all pages, and `milestones`/`results`/
  `index` status updated.
- **Tests**: `tests/test_llm.py` (31) — **274 total** (1 skipped without `matplotlib`).

## Design notes / decisions

- **Off the pipeline, on purpose.** The LLM is an *adapter you can opt into*, not a
  step the default path depends on — consistent with the project's claim that
  evidence is made inspectable without an opaque model in the loop. `info` and the
  CLI state this explicitly.
- **The guard runs first.** `generate()` calls `CostGuard.authorize` before
  `_invoke`, so an over-budget call is refused before any backend (or network) is
  touched — a test pins that the spy backend's invoke count stays `0`. The default
  `max_cost_usd=0.0` means nothing that costs money runs out of the box; the free
  mock is always authorized.
- **Pricing is never hardcoded.** The real adapter requires the caller to pass
  current `Pricing` explicitly; the project ships no vendor price list it could
  silently drift from. `ILLUSTRATIVE_PRICING` is a labeled convenience for demos.
- **Disabled-by-default with two gates.** The Anthropic adapter raises
  `LLMDisabledError` before building/using its client unless `allow_network=True`,
  exactly like the opt-in live connector; the client is injectable so the parse path
  is fully tested offline with no `anthropic` package.
- **Least-trusted provenance.** Model output is `unsupported_hypothesis` and stamped
  `llm:<adapter>`; the four levels are never collapsed and the model never speaks as
  a transparent baseline.
- **Determinism.** The mock is a pure function of the request; the cache key is a
  content hash and cache files are canonical JSON — so a mock run and a cached run
  are byte-stable.

## Validation

```bash
python3 -m pytest -q                                   # 274 passed, 1 skipped (offline)
python3 scripts/08_llm_adapter_demo.py                 # full contract, offline, no API
ruff check src/bioscientist_os/llm src/bioscientist_os/cli.py \
    scripts/08_llm_adapter_demo.py tests/test_llm.py   # clean
biosci llm info
biosci llm complete "Summarize senescence ↔ inflammation evidence." --task polish
biosci llm complete "expensive" --input-price 3 --output-price 15 \
    --max-output-tokens 4000 --max-cost-usd 0.0001     # refused (exit 1)
```

The 31 LLM tests pin: the token estimate and pricing arithmetic; the stable,
content-sensitive request cache key and request validation; the cost guard's
worst-case estimate, under-budget authorization, **over-budget refusal before any
invoke**, and spend accumulation; the mock adapter's determinism, usage, zero/priced
cost, custom responder, and `unsupported_hypothesis` provenance; the dry-run making
no call yet reporting an estimate; the cache miss→`fixture`/hit→`cache` round-trip,
the free-and-unbilled hit, the canonical on-disk JSON, and offline serving with a
dead inner; the Anthropic adapter being off by default (raising before any client
use) and, with an injected client, parsing/pricing/stamping `live`; and the
`biosci llm` CLI (info, complete text/JSON, dry-run, over-budget exit 1, cache
round-trip, unknown-adapter exit 2). All tests are offline (no network, no paid API,
no GPU); the `anthropic` package is not required.

## Status

**Complete.** Next: **Milestone 11 — Website, final report, and portfolio polish**
(update README, docs, and the multi-page website to reflect what exists, what is
prototype-only, the measured results, the explicit non-claims, and the path to a
research paper).
