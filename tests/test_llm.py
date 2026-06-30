"""Tests for the optional, cost-guarded LLM adapter layer (Milestone 10).

The milestone calls for an adapter interface, a **mock** adapter used in all tests,
a cost guard (``--max-cost-usd``, dry-run), a response cache, disabled-by-default
behavior, and no paid API in CI. These tests pin the properties that make the layer
safe and offline:

* the value objects are deterministic — a request hashes to a stable cache key, and
  the token estimate / pricing arithmetic are exact and transparent;
* the cost guard pre-prices a call at the worst case and **refuses over-budget calls
  before any backend is touched**; it accumulates the actual spend; a dry-run never
  invokes the backend and returns an estimate;
* the mock adapter is deterministic and offline, computes usage, costs nothing by
  default, and stamps model output as an *unsupported hypothesis* (``llm:mock``);
* the cache is offline-first and free on a hit (no inner call, no budget charge),
  canonical on disk, and serves with the inner adapter gone;
* the Anthropic adapter is OFF by default (raises before any client use) and, with
  an injected fake client, parses, prices, and stamps ``live`` correctly;
* the ``biosci llm`` CLI surfaces the guard, the cache, and the safety framing.

Everything runs offline from tiny in-test objects; no socket is ever opened and no
``anthropic`` package is required.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from bioscientist_os.cli import app
from bioscientist_os.llm import (
    DEFAULT_ANTHROPIC_MODEL,
    ILLUSTRATIVE_PRICING,
    AnthropicLLMAdapter,
    CachedLLMAdapter,
    CostGuard,
    CostGuardError,
    LLMAdapter,
    LLMDisabledError,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    MockLLMAdapter,
    Pricing,
    anthropic_adapter,
    estimate_tokens,
)
from bioscientist_os.schemas import DataSource, EpistemicLevel

runner = CliRunner()


# --- a spy adapter to prove the guard / dry-run never reach the backend ----


class _SpyAdapter(LLMAdapter):
    """A minimal adapter that counts how many times the backend is invoked."""

    name = "spy"
    provider = "spy"
    live = False

    def __init__(self, *, pricing: Pricing, max_cost_usd: float = 0.0, dry_run: bool = False):
        self.pricing = pricing
        self.default_model = "spy-1"
        self.guard = CostGuard(pricing, max_cost_usd=max_cost_usd, dry_run=dry_run)
        self.calls = 0

    def _invoke(self, request: LLMRequest, model: str) -> tuple[str, LLMUsage]:
        self.calls += 1
        return "spy-out", LLMUsage(input_tokens=10, output_tokens=5)


# --- token estimate -------------------------------------------------------


def test_estimate_tokens_is_transparent_and_monotone() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2  # ceil(5/4)
    assert estimate_tokens("x" * 400) == 100
    assert estimate_tokens("a" * 100) >= estimate_tokens("a" * 50)


# --- pricing --------------------------------------------------------------


def test_pricing_cost_math() -> None:
    p = Pricing(input_usd_per_mtok=3.0, output_usd_per_mtok=15.0)
    assert p.cost(1_000_000, 0) == pytest.approx(3.0)
    assert p.cost(0, 1_000_000) == pytest.approx(15.0)
    assert p.cost(500_000, 200_000) == pytest.approx(1.5 + 3.0)


def test_pricing_zero_is_free() -> None:
    assert Pricing.zero().cost(10_000, 10_000) == 0.0


# --- request / cache key --------------------------------------------------


def test_request_cache_key_is_stable_and_content_sensitive() -> None:
    a = LLMRequest(prompt="hello", system="sys", task="t", model="m")
    b = LLMRequest(prompt="hello", system="sys", task="t", model="m")
    c = LLMRequest(prompt="hello!", system="sys", task="t", model="m")
    assert a.cache_key() == b.cache_key()
    assert a.cache_key() != c.cache_key()
    assert len(a.cache_key()) == 64  # sha256 hex


def test_request_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        LLMRequest(prompt="   ")
    with pytest.raises(ValueError):
        LLMRequest(prompt="ok", max_output_tokens=0)
    with pytest.raises(ValueError):
        LLMRequest(prompt="ok", temperature=3.0)


# --- cost guard -----------------------------------------------------------


def test_cost_guard_estimate_uses_worst_case_output() -> None:
    guard = CostGuard(Pricing(3.0, 15.0), max_cost_usd=10.0)
    req = LLMRequest(prompt="abcd", system="", max_output_tokens=1000)
    est = guard.estimate(req)
    assert est.input_tokens == estimate_tokens("abcd")
    assert est.output_tokens == 1000  # worst case = the cap, not the actual output
    assert est.usd == pytest.approx(Pricing(3.0, 15.0).cost(est.input_tokens, 1000))


def test_cost_guard_authorizes_under_budget_and_zero_priced() -> None:
    guard = CostGuard(Pricing.zero(), max_cost_usd=0.0)
    # a free call is authorized even with a $0 budget (exact-equality tolerance)
    assert guard.authorize(LLMRequest(prompt="hi")).usd == 0.0


def test_cost_guard_blocks_over_budget_before_invoke() -> None:
    spy = _SpyAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=0.0001)
    with pytest.raises(CostGuardError) as exc:
        spy.generate(LLMRequest(prompt="x" * 4000, max_output_tokens=4000))
    assert spy.calls == 0  # refused before the backend was touched
    assert exc.value.estimate.usd > 0.0001


def test_cost_guard_accumulates_spend_across_calls() -> None:
    spy = _SpyAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=10.0)
    spy.generate(LLMRequest(prompt="one"))
    first = spy.guard.spent_usd
    spy.generate(LLMRequest(prompt="two"))
    assert spy.guard.spent_usd > first
    expected = Pricing(3.0, 15.0).cost(10, 5) * 2  # spy reports (10, 5) per call
    assert spy.guard.spent_usd == pytest.approx(expected)
    assert spy.calls == 2


# --- mock adapter ---------------------------------------------------------


def test_mock_adapter_is_deterministic_offline() -> None:
    m = MockLLMAdapter()
    req = LLMRequest(prompt="line one\nline two", task="polish")
    a = m.generate(req)
    b = m.generate(req)
    assert a.text == b.text
    assert "MOCK LLM OUTPUT" in a.text
    assert "signature:" in a.text


def test_mock_adapter_usage_and_zero_cost_by_default() -> None:
    m = MockLLMAdapter()
    resp = m.generate(LLMRequest(prompt="senescence and inflammation"))
    assert resp.cost_usd == 0.0
    assert resp.usage.input_tokens > 0
    assert resp.usage.output_tokens > 0
    assert resp.data_source is DataSource.fixture
    assert resp.provider == "mock" and resp.live is False


def test_mock_adapter_priced_cost_is_recorded() -> None:
    m = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=1.0)
    resp = m.generate(LLMRequest(prompt="senescence"))
    expected = Pricing(3.0, 15.0).cost(resp.usage.input_tokens, resp.usage.output_tokens)
    assert resp.cost_usd == pytest.approx(expected)
    assert m.guard.spent_usd == pytest.approx(expected)


def test_mock_output_is_unsupported_hypothesis_provenance() -> None:
    m = MockLLMAdapter()
    resp = m.generate(LLMRequest(prompt="hi"))
    prov = resp.to_provenance(paper_id="biosci-paper-001")
    assert prov.epistemic_level is EpistemicLevel.unsupported_hypothesis
    assert prov.extraction_method == "llm:mock:mock-llm-1"
    assert prov.data_source is DataSource.fixture
    assert prov.paper_id == "biosci-paper-001"


def test_custom_responder_is_used() -> None:
    m = MockLLMAdapter(responder=lambda req, model: f"R:{req.prompt}:{model}")
    resp = m.generate(LLMRequest(prompt="abc", model="zz"))
    assert resp.text == "R:abc:zz"


# --- dry run --------------------------------------------------------------


def test_dry_run_does_not_invoke_and_returns_estimate() -> None:
    spy = _SpyAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=10.0, dry_run=True)
    resp = spy.generate(LLMRequest(prompt="estimate me", max_output_tokens=200))
    assert spy.calls == 0  # no backend call
    assert resp.dry_run is True
    assert resp.text == ""
    assert resp.usage.estimated is True
    assert resp.usage.output_tokens == 200  # the worst-case cap
    assert spy.guard.spent_usd == 0.0  # dry-run spends nothing
    assert resp.cost_usd > 0.0  # ... but reports what it *would* cost


# --- cache ----------------------------------------------------------------


def test_cache_miss_then_hit(tmp_path) -> None:
    inner = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=1.0)
    cache = CachedLLMAdapter(inner, tmp_path)
    req = LLMRequest(prompt="cache me", task="polish")
    assert not cache.is_cached(req)

    miss = cache.generate(req)
    assert miss.served_from_cache is False
    assert miss.data_source is DataSource.fixture  # the bytes really came from the mock
    assert cache.is_cached(req)

    hit = cache.generate(req)
    assert hit.served_from_cache is True
    assert hit.data_source is DataSource.cache
    assert hit.text == miss.text
    assert cache.cached_keys() == [req.cache_key()]


def test_cache_hit_is_free_and_does_not_charge_budget(tmp_path) -> None:
    inner = MockLLMAdapter(pricing=Pricing(3.0, 15.0), max_cost_usd=1.0)
    cache = CachedLLMAdapter(inner, tmp_path)
    req = LLMRequest(prompt="charge once")
    cache.generate(req)
    spent_after_miss = inner.guard.spent_usd
    assert spent_after_miss > 0.0

    hit = cache.generate(req)
    assert hit.cost_usd == 0.0
    assert inner.guard.spent_usd == spent_after_miss  # the hit charged nothing


def test_cache_file_is_canonical_and_round_trips(tmp_path) -> None:
    inner = MockLLMAdapter()
    cache = CachedLLMAdapter(inner, tmp_path)
    req = LLMRequest(prompt="canonical")
    cache.generate(req)
    path = next(tmp_path.rglob("*.json"))
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) == text
    assert data["request_key"] == req.cache_key()
    assert data["provider"] == "mock"


def test_cache_serves_offline_when_inner_is_dead(tmp_path) -> None:
    warm = CachedLLMAdapter(MockLLMAdapter(), tmp_path)
    req = LLMRequest(prompt="warm me")
    warm.generate(req)

    class _DeadAdapter(LLMAdapter):
        name = "mock"
        provider = "mock"
        live = False

        def __init__(self) -> None:
            self.pricing = Pricing.zero()
            self.default_model = "mock-llm-1"
            self.guard = CostGuard(self.pricing, max_cost_usd=0.0)

        def _invoke(self, request, model):
            raise AssertionError("inner adapter should not be called on a cache hit")

    dead = CachedLLMAdapter(_DeadAdapter(), tmp_path)
    served = dead.generate(req)
    assert served.served_from_cache is True
    assert served.data_source is DataSource.cache


# --- anthropic adapter (opt-in, offline) ----------------------------------


class _FakeAnthropicClient:
    """A tiny stand-in for ``anthropic.Anthropic`` to exercise _invoke offline."""

    def __init__(self, text: str = "fake reply", in_tok: int = 7, out_tok: int = 4) -> None:
        self.calls = 0
        self._text = text
        self._in = in_tok
        self._out = out_tok
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._text)],
            usage=SimpleNamespace(input_tokens=self._in, output_tokens=self._out),
        )


def test_anthropic_disabled_by_default_raises_before_client() -> None:
    client = _FakeAnthropicClient()
    adapter = AnthropicLLMAdapter(
        pricing=ILLUSTRATIVE_PRICING[DEFAULT_ANTHROPIC_MODEL],
        allow_network=False,
        max_cost_usd=10.0,  # enough budget so the guard is not what blocks us
        client=client,
    )
    with pytest.raises(LLMDisabledError):
        adapter.generate(LLMRequest(prompt="hello"))
    assert client.calls == 0  # never reached the client


def test_anthropic_factory_is_off_by_default() -> None:
    # Budget headroom so the *disabled* gate (not the cost guard) is what blocks us;
    # with the default $0 budget and non-zero pricing the guard would fire first,
    # which is also a valid "this will not call out" outcome.
    adapter = anthropic_adapter(pricing=Pricing(1.0, 5.0), max_cost_usd=10.0)
    assert adapter.allow_network is False
    assert adapter.live is True
    assert adapter.default_model == DEFAULT_ANTHROPIC_MODEL
    with pytest.raises(LLMDisabledError):
        adapter.generate(LLMRequest(prompt="hi"))


def test_anthropic_injected_client_parses_and_stamps_live() -> None:
    client = _FakeAnthropicClient(text="senescence summary", in_tok=11, out_tok=6)
    pricing = Pricing(3.0, 15.0)
    adapter = AnthropicLLMAdapter(
        pricing=pricing, allow_network=True, max_cost_usd=10.0, client=client, model="claude-x"
    )
    resp = adapter.generate(LLMRequest(prompt="summarize", system="be terse"))
    assert client.calls == 1
    assert client.last_kwargs["model"] == "claude-x"
    assert client.last_kwargs["messages"] == [{"role": "user", "content": "summarize"}]
    assert resp.text == "senescence summary"
    assert resp.usage.input_tokens == 11 and resp.usage.output_tokens == 6
    assert resp.data_source is DataSource.live
    assert resp.cost_usd == pytest.approx(pricing.cost(11, 6))
    assert resp.to_provenance().epistemic_level is EpistemicLevel.unsupported_hypothesis


def test_illustrative_pricing_covers_default_model() -> None:
    assert DEFAULT_ANTHROPIC_MODEL in ILLUSTRATIVE_PRICING
    p = ILLUSTRATIVE_PRICING[DEFAULT_ANTHROPIC_MODEL]
    assert p.input_usd_per_mtok > 0 and p.output_usd_per_mtok > 0


# --- response serialization ------------------------------------------------


def test_response_to_dict_is_complete() -> None:
    resp = LLMResponse(
        text="t", model="m", usage=LLMUsage(3, 2), cost_usd=0.0,
        adapter="mock", provider="mock", live=False, request_key="k",
    )
    d = resp.to_dict()
    assert d["data_source"] == "fixture"
    assert d["epistemic_level"] == "unsupported_hypothesis"
    assert d["extraction_method"] == "llm:mock:m"
    assert d["usage"]["total_tokens"] == 5


# --- CLI: biosci llm ------------------------------------------------------


def test_cli_llm_info() -> None:
    res = runner.invoke(app, ["llm", "info"])
    assert res.exit_code == 0, res.output
    out = res.output.lower()
    assert "off the default path" in out
    assert "cost guard" in out
    assert "disabled by default" in out
    assert "unsupported hypothesis" in out


def test_cli_llm_complete_text() -> None:
    res = runner.invoke(app, ["llm", "complete", "Does senescence drive inflammation?"])
    assert res.exit_code == 0, res.output
    assert "MOCK LLM OUTPUT" in res.output
    assert "cost: $0.000000" in res.output
    assert "UNSUPPORTED HYPOTHESIS" in res.output


def test_cli_llm_complete_json() -> None:
    res = runner.invoke(app, ["llm", "complete", "hello", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["adapter"] == "mock"
    assert payload["epistemic_level"] == "unsupported_hypothesis"
    assert payload["data_source"] == "fixture"
    assert "MOCK LLM OUTPUT" in payload["text"]


def test_cli_llm_complete_dry_run() -> None:
    res = runner.invoke(
        app,
        ["llm", "complete", "estimate me", "--input-price", "3", "--output-price", "15",
         "--max-cost-usd", "9", "--dry-run"],
    )
    assert res.exit_code == 0, res.output
    assert "dry_run=True" in res.output
    assert "no call was made" in res.output


def test_cli_llm_complete_over_budget_exits_1() -> None:
    res = runner.invoke(
        app,
        ["llm", "complete", "expensive", "--input-price", "3", "--output-price", "15",
         "--max-output-tokens", "4000", "--max-cost-usd", "0.0000001"],
    )
    assert res.exit_code == 1
    assert "cost guard" in res.output


def test_cli_llm_complete_cache_round_trip(tmp_path) -> None:
    cache_dir = tmp_path / "llmcache"
    args = ["llm", "complete", "cache via cli", "--cache", "--cache-dir", str(cache_dir), "--json"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert json.loads(first.output)["served_from_cache"] is False

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["served_from_cache"] is True
    assert payload["data_source"] == "cache"
    assert list(cache_dir.rglob("*.json"))


def test_cli_llm_unknown_adapter_exits_2() -> None:
    res = runner.invoke(app, ["llm", "complete", "x", "--adapter", "openai"])
    assert res.exit_code == 2
    assert "only 'mock' is available" in res.output
