"""Tests for the offline-first database connector layer (Milestone 6).

The milestone calls for a base connector interface, a required fixture-backed
connector, a gitignored cache layer, retry/error handling, and a provenance field
(``data_source`` ∈ fixture / cache / live) on every record. These tests pin the
properties that make the layer trustworthy and offline-safe:

* the fixture connectors serve the right records, keyed by id, always stamped
  ``fixture`` — and a missing id is ``None``/``RecordNotFound``, never a guess;
* the cache is genuinely offline-first: a cache hit reports ``cache`` and needs no
  inner connector, while the first fetch honestly reports where the bytes came from;
* retry/error handling retries only transient failures, with a deterministic
  injected sleep, and wraps an exhausted retry budget — no network, no real sleeping;
* the live connector is OFF by default (it raises before any transport call) and,
  with an injected mock transport, parses, retries, and stamps ``live`` correctly;
* the ``biosci db`` CLI surfaces the ``data_source`` provenance and the error paths.

Everything runs offline from the committed fixtures or tiny in-test objects; no
socket is ever opened.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bioscientist_os import fixtures
from bioscientist_os.cli import app
from bioscientist_os.databases import (
    BaseConnector,
    CachedConnector,
    ConnectorError,
    ConnectorRegistry,
    FixtureConnector,
    PermanentConnectorError,
    RecordNotFound,
    TransientConnectorError,
    call_with_retries,
    connectors_from_records,
    load_connectors,
    open_connectors,
    paper_connector,
    uniprot_connector,
    with_data_source,
)
from bioscientist_os.databases.live import (
    LiveConnector,
    parse_uniprot_json,
    uniprot_live_connector,
)
from bioscientist_os.ingest import ingest_fixtures
from bioscientist_os.schemas import DatabaseRecord, DataSource, Paper

runner = CliRunner()


# --- fixtures / helpers ---------------------------------------------------


@pytest.fixture(scope="module")
def bundle() -> fixtures.FixtureBundle:
    return fixtures.load_all()


@pytest.fixture(scope="module")
def registry(bundle: fixtures.FixtureBundle) -> ConnectorRegistry:
    return connectors_from_records(bundle.papers, bundle.proteins + bundle.associations)


@pytest.fixture(scope="module")
def cli_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db = tmp_path_factory.mktemp("connectorcli") / "bioscientist.db"
    ingest_fixtures(db_path=db)
    return db


# A tiny UniProtKB-shaped JSON body, used to exercise the live parse path offline.
_UNIPROT_JSON = {
    "primaryAccession": "P05231",
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Interleukin-6"}}},
    "genes": [{"geneName": {"value": "IL6"}}],
    "organism": {"scientificName": "Homo sapiens"},
}


class _SpyConnector(BaseConnector[DatabaseRecord]):
    """A minimal connector that counts fetches and can be made to fail.

    Used to prove the cache does (or does not) reach its inner connector.
    """

    def __init__(
        self, records: list[DatabaseRecord], *, source: str = "UniProt", fail: bool = False
    ) -> None:
        self.source = source
        self.record_type = "protein"
        self.record_model = DatabaseRecord
        self.data_source = DataSource.fixture
        self._by_id = {r.record_id: r for r in records}
        self.calls = 0
        self.fail = fail

    def fetch(self, record_id: str) -> DatabaseRecord | None:
        self.calls += 1
        if self.fail:
            raise AssertionError("inner connector should not have been called")
        return self._by_id.get(record_id)

    def ids(self) -> list[str]:
        return sorted(self._by_id)


# --- provenance stamping --------------------------------------------------


def test_with_data_source_stamps_and_preserves_synthetic(bundle) -> None:
    rec = bundle.proteins[0]
    cached = with_data_source(rec, DataSource.cache)
    assert cached.data_source is DataSource.cache
    assert cached.synthetic == rec.synthetic  # orthogonal axis, untouched
    # identity short-circuit when already the requested source (no needless copy)
    assert with_data_source(cached, DataSource.cache) is cached


# --- FixtureConnector -----------------------------------------------------


def test_uniprot_connector_serves_proteins_stamped_fixture(bundle) -> None:
    conn = uniprot_connector(bundle.proteins + bundle.associations)
    assert conn.source == "UniProt"
    assert conn.record_type == "protein"
    assert len(conn) == 10  # only the UniProt records, not the associations
    il6 = conn.get("P05231")
    assert il6.fields["protein_name"] == "Interleukin-6"
    assert il6.data_source is DataSource.fixture
    assert il6.synthetic is False
    assert "P05231" in conn and "OTAF-0002" not in conn


def test_paper_connector_serves_papers_by_id(bundle) -> None:
    conn = paper_connector(bundle.papers)
    assert conn.record_model is Paper
    paper = conn.get("biosci-paper-001")
    assert isinstance(paper, Paper)
    assert paper.data_source is DataSource.fixture
    assert len(conn.ids()) == len(bundle.papers)


def test_fetch_missing_is_none_and_get_raises(registry) -> None:
    conn = registry.get("uniprot")
    assert conn.fetch("NOPE") is None
    with pytest.raises(RecordNotFound) as exc:
        conn.get("NOPE")
    assert exc.value.source == "UniProt"
    assert exc.value.record_id == "NOPE"


def test_fetch_many_drops_absent_keeps_order(registry) -> None:
    conn = registry.get("uniprot")
    got = conn.fetch_many(["P05231", "NOPE", "P04637"])
    assert [r.record_id for r in got] == ["P05231", "P04637"]


def test_fixture_connector_first_id_wins_on_collision() -> None:
    a = DatabaseRecord(record_id="X", source="S", record_type="t", fields={"v": 1}, synthetic=True)
    b = DatabaseRecord(record_id="X", source="S", record_type="t", fields={"v": 2}, synthetic=True)
    conn = FixtureConnector(
        "S", "t", [a, b], key=lambda r: r.record_id, record_model=DatabaseRecord
    )
    assert conn.get("X").fields["v"] == 1  # first-inserted wins (documented, stable)


def test_ids_are_sorted(registry) -> None:
    ids = registry.get("uniprot").ids()
    assert ids == sorted(ids)


# --- registry / entry points ----------------------------------------------


def test_registry_names_and_counts(registry) -> None:
    assert registry.names() == ["opentargets", "papers", "uniprot"]
    counts = {row["name"]: row["count"] for row in registry.describe()}
    assert counts == {"uniprot": 10, "opentargets": 9, "papers": 18}
    assert all(row["data_source"] == "fixture" for row in registry.describe())


def test_registry_unknown_name_raises(registry) -> None:
    with pytest.raises(KeyError):
        registry.get("ensembl")
    assert "ensembl" not in registry


def test_load_connectors_matches_open_connectors(cli_db, registry) -> None:
    from_fixtures = load_connectors()
    from_db = open_connectors(cli_db)
    for name in registry.names():
        assert from_fixtures.get(name).ids() == from_db.get(name).ids()
    # a freshly built db agrees with the committed fixtures on a sample record
    assert from_db.get("uniprot").get("P05231").fields["gene"] == "IL6"


def test_open_connectors_rejects_non_database(tmp_path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    with pytest.raises(ValueError, match="not a bioscientist-os database"):
        open_connectors(empty)


# --- CachedConnector (offline-first) --------------------------------------


def test_cache_miss_returns_inner_source_then_hit_returns_cache(bundle, tmp_path) -> None:
    inner = uniprot_connector(bundle.proteins)
    cache = CachedConnector(inner, tmp_path)
    assert not cache.is_cached("P05231")

    first = cache.fetch("P05231")
    assert first.data_source is DataSource.fixture  # the bytes really came from fixture
    assert cache.is_cached("P05231")  # ... and a cache copy was written

    second = cache.fetch("P05231")
    assert second.data_source is DataSource.cache  # served from the local file
    assert second.fields["protein_name"] == "Interleukin-6"
    assert cache.cached_ids() == ["P05231"]


def test_cache_hit_does_not_touch_inner_connector(bundle, tmp_path) -> None:
    inner = _SpyConnector(list(bundle.proteins))
    cache = CachedConnector(inner, tmp_path)
    cache.fetch("P05231")
    assert inner.calls == 1  # miss reached inner once
    cache.fetch("P05231")
    assert inner.calls == 1  # hit served entirely from the cache file


def test_cache_serves_offline_when_inner_is_unavailable(bundle, tmp_path) -> None:
    # Warm the cache with a working inner, then point a new cache at the same dir with
    # a "dead" inner: the warmed record is still served (offline-first), no inner call.
    warm = CachedConnector(uniprot_connector(bundle.proteins), tmp_path)
    warm.fetch("P05231")
    dead = CachedConnector(_SpyConnector([], fail=True), tmp_path)
    served = dead.fetch("P05231")
    assert served.data_source is DataSource.cache
    assert served.record_id == "P05231"


def test_cache_miss_on_absent_writes_nothing(bundle, tmp_path) -> None:
    cache = CachedConnector(uniprot_connector(bundle.proteins), tmp_path)
    assert cache.fetch("NOPE") is None
    assert cache.cached_ids() == []


def test_cache_file_is_canonical_and_round_trips(bundle, tmp_path) -> None:
    cache = CachedConnector(uniprot_connector(bundle.proteins), tmp_path)
    cache.fetch("P05231")
    path = next(tmp_path.rglob("*.json"))
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["data_source"] == "cache"  # the written copy is stamped cache
    # canonical: sorted keys, deterministic
    assert json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) == text
    # round-trips back into the typed model
    restored = DatabaseRecord.model_validate_json(text)
    assert restored.record_id == "P05231"


# --- retry / error handling -----------------------------------------------


def test_call_with_retries_returns_immediately_on_success() -> None:
    slept: list[float] = []
    assert call_with_retries(lambda: 42, retries=3, sleep=slept.append) == 42
    assert slept == []  # no failure, no backoff


def test_call_with_retries_retries_transient_then_succeeds() -> None:
    state = {"n": 0}

    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise TransientConnectorError("temporary")
        return "ok"

    slept: list[float] = []
    assert call_with_retries(flaky, retries=2, base_delay=0.5, sleep=slept.append) == "ok"
    assert state["n"] == 3
    assert slept == [0.5, 1.0]  # exponential backoff, deterministic


def test_call_with_retries_wraps_exhausted_budget() -> None:
    def always_transient() -> None:
        raise TransientConnectorError("still failing")

    with pytest.raises(ConnectorError, match="after 3 attempt"):
        call_with_retries(always_transient, retries=2, sleep=lambda _s: None)


def test_call_with_retries_does_not_retry_permanent() -> None:
    state = {"n": 0}

    def permanent() -> None:
        state["n"] += 1
        raise PermanentConnectorError("bad request")

    with pytest.raises(PermanentConnectorError):
        call_with_retries(permanent, retries=5, sleep=lambda _s: None)
    assert state["n"] == 1  # raised on the first attempt, never retried


# --- LiveConnector (opt-in, mock transport, offline) ----------------------


def _live(transport, **kw) -> LiveConnector:
    return LiveConnector(
        "UniProt",
        "protein",
        "https://example.test/{id}.json",
        parse_uniprot_json,
        DatabaseRecord,
        transport=transport,
        sleep=lambda _s: None,
        **kw,
    )


def test_live_connector_disabled_by_default_raises_before_transport() -> None:
    calls: list[str] = []
    conn = _live(lambda url: calls.append(url), allow_network=False)
    with pytest.raises(PermanentConnectorError, match="disabled"):
        conn.fetch("P05231")
    assert calls == []  # no transport call happened


def test_uniprot_live_connector_factory_is_off_by_default() -> None:
    conn = uniprot_live_connector()
    assert conn.allow_network is False
    assert conn.data_source is DataSource.live
    with pytest.raises(PermanentConnectorError):
        conn.fetch("P05231")


def test_live_connector_parses_and_stamps_live() -> None:
    seen: list[str] = []

    def transport(url: str) -> str:
        seen.append(url)
        return json.dumps(_UNIPROT_JSON)

    conn = _live(transport, allow_network=True)
    rec = conn.get("P05231")
    assert seen == ["https://example.test/P05231.json"]  # id URL-quoted into template
    assert rec.fields["protein_name"] == "Interleukin-6"
    assert rec.fields["gene"] == "IL6"
    assert rec.data_source is DataSource.live


def test_live_connector_404_is_not_found_not_error() -> None:
    conn = _live(lambda url: None, allow_network=True)
    assert conn.fetch("MISSING") is None
    with pytest.raises(RecordNotFound):
        conn.get("MISSING")


def test_live_connector_retries_transient_then_succeeds() -> None:
    state = {"n": 0}

    def transport(url: str) -> str:
        state["n"] += 1
        if state["n"] < 2:
            raise TransientConnectorError("503")
        return json.dumps(_UNIPROT_JSON)

    conn = _live(transport, allow_network=True, retries=2)
    assert conn.fetch("P05231").fields["gene"] == "IL6"
    assert state["n"] == 2


def test_live_connector_wraps_exhausted_retries() -> None:
    def transport(url: str) -> str:
        raise TransientConnectorError("503")

    conn = _live(transport, allow_network=True, retries=1)
    with pytest.raises(ConnectorError):
        conn.fetch("P05231")


def test_live_connector_is_not_enumerable() -> None:
    conn = _live(lambda url: None, allow_network=True)
    with pytest.raises(PermanentConnectorError, match="not enumerable"):
        conn.ids()


# --- CLI: biosci db -------------------------------------------------------


def test_cli_db_sources(cli_db) -> None:
    res = runner.invoke(app, ["db", "sources", "--db", str(cli_db)])
    assert res.exit_code == 0, res.output
    assert "uniprot" in res.output and "records=10" in res.output
    assert "papers" in res.output and "records=18" in res.output
    assert "data_source=fixture" in res.output


def test_cli_db_list(cli_db) -> None:
    res = runner.invoke(app, ["db", "list", "--source", "uniprot", "--db", str(cli_db)])
    assert res.exit_code == 0, res.output
    assert "P05231" in res.output
    assert "10 record id" in res.output


def test_cli_db_lookup_text_and_provenance(cli_db) -> None:
    res = runner.invoke(
        app, ["db", "lookup", "--source", "uniprot", "--id", "P05231", "--db", str(cli_db)]
    )
    assert res.exit_code == 0, res.output
    assert "data_source=fixture" in res.output
    assert "Interleukin-6" in res.output
    assert "Not a clinical or diagnostic data source" in res.output  # safety framing


def test_cli_db_lookup_json(cli_db) -> None:
    args = ["db", "lookup", "--source", "opentargets", "--id", "OTAF-0002", "--db", str(cli_db)]
    res = runner.invoke(app, [*args, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["record_id"] == "OTAF-0002"
    assert payload["data_source"] == "fixture"
    assert payload["record"]["fields"]["target_gene"] == "IL6"


def test_cli_db_lookup_cache_round_trip(cli_db, tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    args = [
        "db", "lookup", "--source", "uniprot", "--id", "P05231",
        "--db", str(cli_db), "--cache", "--cache-dir", str(cache_dir),
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert "data_source=fixture" in first.output  # miss: served from the real source

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.output
    assert "data_source=cache" in second.output  # hit: served from the local cache
    assert list(cache_dir.rglob("*.json"))  # a cache file was written


def test_cli_db_lookup_unknown_source_exits_2(cli_db) -> None:
    res = runner.invoke(app, ["db", "lookup", "--source", "nope", "--id", "x", "--db", str(cli_db)])
    assert res.exit_code == 2
    assert "unknown source" in res.output


def test_cli_db_lookup_unknown_id_exits_1(cli_db) -> None:
    res = runner.invoke(
        app, ["db", "lookup", "--source", "uniprot", "--id", "ZZZ", "--db", str(cli_db)]
    )
    assert res.exit_code == 1
    assert "no record 'ZZZ'" in res.output


def test_cli_db_on_uninitialized_db_errors(tmp_path) -> None:
    empty = tmp_path / "empty.db"
    empty.touch()
    res = runner.invoke(app, ["db", "sources", "--db", str(empty)])
    assert res.exit_code == 1
    assert "not a bioscientist-os database" in res.output
