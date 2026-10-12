"""Read-time source liveness and cache invalidation on revoke (MEMORY_SOURCE_LINEAGE_ENABLED).

* Memories whose source connector is deleted, revoked, disconnected or gone never
  reach recall (agent, department, workspace, hybrid) even before the purge runs,
  and the filter fails closed.
* Customer observations from a revoked connector, and the signals built only on
  them, never reach the account card or account health.
* A disconnect makes the retrieval, instant-answer, source-summary and connector
  read caches miss, and clears the in-process caches of the org.
* Untagged (legacy) rows are kept as they are: never hidden, retired or accepted.
* With the flag off nothing changes and no extra read is made.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from app.services import memory_source_liveness as msl

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "22222222-2222-4222-8222-222222222222"
LIVE = "aaaaaaaa-0000-4000-8000-000000000001"
DELETED = "aaaaaaaa-0000-4000-8000-000000000002"
REVOKED = "aaaaaaaa-0000-4000-8000-000000000003"
FOREIGN = "aaaaaaaa-0000-4000-8000-000000000004"
GONE = "aaaaaaaa-0000-4000-8000-000000000005"
ON = SimpleNamespace(memory_source_lineage_enabled=True)
OFF = SimpleNamespace(memory_source_lineage_enabled=False)

CONNECTORS = [
    {"id": LIVE, "org_id": ORG, "status": "connected", "deleted_at": None},
    {"id": DELETED, "org_id": ORG, "status": "disconnected", "deleted_at": "2026-10-12T10:00:00+00:00"},
    {"id": REVOKED, "org_id": ORG, "status": "revoked", "deleted_at": None},
    {"id": FOREIGN, "org_id": OTHER_ORG, "status": "connected", "deleted_at": None},
]


class _Query:
    def __init__(self, db: _DB, table: str) -> None:
        self.db, self.table, self.filters, self.in_filter = db, table, [], None
        self.columns = ""
        self._update: dict[str, Any] | None = None

    def select(self, columns: str = "*") -> _Query:
        self.columns = columns
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self._update = payload
        return self

    def eq(self, key: str, value: Any) -> _Query:
        self.filters.append((key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> _Query:
        self.in_filter = (key, set(values))
        return self

    def __getattr__(self, name: str):  # order, limit, or_, gte, is_ ... are no-ops here
        return lambda *a, **k: self

    def execute(self) -> SimpleNamespace:
        self.db.reads.append((self.table, self.columns, self.in_filter))
        if self.db.fail_on == self.table:
            raise RuntimeError(f"{self.table} read failed")
        rows = [dict(r) for r in self.db.tables.get(self.table, [])]
        for key, value in self.filters:
            rows = [r for r in rows if str(r.get(key)) == str(value)]
        if self.in_filter:
            key, values = self.in_filter
            rows = [r for r in rows if str(r.get(key)) in {str(v) for v in values}]
        if self._update is not None:
            return SimpleNamespace(data=rows)
        return SimpleNamespace(data=rows)


class _DB:
    def __init__(self, tables: dict[str, list[dict[str, Any]]], *, rpc_rows: list[dict[str, Any]] | None = None):
        self.tables = tables
        self.rpc_rows = rpc_rows or []
        self.reads: list[tuple[str, str, Any]] = []
        self.fail_on: str | None = None

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rpc(self, name: str, params: dict[str, Any]) -> SimpleNamespace:
        self.reads.append(("rpc:" + name, "", None))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[dict(r) for r in self.rpc_rows]))


def _memories() -> list[dict[str, Any]]:
    return [
        dict(m, is_active=True, is_current=True, category="fact")
        for m in _memory_rows()
    ]


def _memory_rows() -> list[dict[str, Any]]:
    return [
        {"id": "m-live", "org_id": ORG, "content": "from live", "source_connector_id": LIVE},
        {"id": "m-deleted", "org_id": ORG, "content": "from deleted", "source_connector_id": DELETED},
        {"id": "m-revoked", "org_id": ORG, "content": "from revoked", "source_connector_id": REVOKED},
        {"id": "m-foreign", "org_id": ORG, "content": "names another org's connector", "source_connector_id": FOREIGN},
        {"id": "m-gone", "org_id": ORG, "content": "connector row gone", "source_connector_id": GONE},
        {"id": "m-legacy", "org_id": ORG, "content": "legacy untagged", "source_connector_id": None},
    ]


def _db() -> _DB:
    return _DB({"agent_memories": _memories(), "connectors": [dict(c) for c in CONNECTORS]})


# ---------------------------------------------------------------- memory filter


def test_flag_off_returns_rows_unchanged_without_any_read():
    db = _db()
    rows = [{"id": m["id"], "content": m["content"]} for m in _memories()]
    assert msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=OFF) is rows
    assert db.reads == []


def test_memories_from_revoked_deleted_foreign_or_missing_connectors_are_dropped():
    db = _db()
    rows = [{"id": m["id"], "content": m["content"]} for m in _memories()]  # no lineage column, as RPCs return
    kept = msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=ON)
    assert [r["id"] for r in kept] == ["m-live", "m-legacy"]
    # One lineage read by id, one connectors read, both org-scoped.
    assert [t for t, _c, _i in db.reads] == ["agent_memories", "connectors"]


def test_rows_carrying_lineage_skip_the_lineage_read():
    db = _db()
    kept = msl.drop_memories_from_revoked_sources(db, ORG, _memories(), settings=ON)
    assert [r["id"] for r in kept] == ["m-live", "m-legacy"]
    assert [t for t, _c, _i in db.reads] == ["connectors"]


def test_rpc_rows_keyed_by_memory_id_are_filtered():
    db = _db()
    rows = [{"memory_id": "m-revoked", "content": "x"}, {"memory_id": "m-live", "content": "y"}]
    kept = msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=ON)
    assert [r["memory_id"] for r in kept] == ["m-live"]


def test_untagged_legacy_memories_are_kept_and_cost_no_connector_read():
    db = _db()
    rows = [{"id": "m-legacy", "content": "legacy untagged"}]
    assert msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=ON) == rows
    assert [t for t, _c, _i in db.reads] == ["agent_memories"]
    # And nothing was written: the filter never retires or accepts anything.
    assert db.tables["agent_memories"] == _memories()


@pytest.mark.parametrize("failing", ["agent_memories", "connectors"])
def test_filter_fails_closed_when_lineage_or_connectors_cannot_be_read(failing):
    db = _db()
    db.fail_on = failing
    rows = [{"id": m["id"], "content": m["content"]} for m in _memories()]
    assert msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=ON) == []


def test_a_memory_not_found_by_id_is_not_shown():
    db = _db()
    rows = [{"id": "m-vanished", "content": "deleted meanwhile"}, {"id": "m-live", "content": "from live"}]
    assert [r["id"] for r in msl.drop_memories_from_revoked_sources(db, ORG, rows, settings=ON)] == ["m-live"]


# ---------------------------------------------------------------- recall paths


@pytest.fixture
def _no_embeddings(monkeypatch):
    from app.services import agent_memory_service as ams

    monkeypatch.setattr(ams, "ensure_agent_in_org", lambda *a, **k: None)
    monkeypatch.setattr(ams, "get_embedding", lambda *a, **k: [0.0, 0.1])


def _rpc_rows() -> list[dict[str, Any]]:
    return [
        {"memory_id": m["id"], "content": m["content"], "category": "fact", "score": 0.9}
        for m in _memories()
    ]


@pytest.mark.parametrize("settings, expected", [(OFF, [m["id"] for m in _memories()]), (ON, ["m-live", "m-legacy"])])
def test_agent_memory_search_never_returns_revoked_source_memories(_no_embeddings, settings, expected):
    from app.services.agent_memory_service import search_agent_memories

    db = _db()
    db.rpc_rows = _rpc_rows()
    out = search_agent_memories(settings, db, ORG, "agent-1", query="renewal", top_k=10)
    assert [r["id"] for r in out] == expected
    if settings is OFF:
        assert not any(t == "connectors" for t, _c, _i in db.reads)


@pytest.mark.parametrize("settings, expected", [(OFF, [m["id"] for m in _memories()]), (ON, ["m-live", "m-legacy"])])
def test_department_memory_search_never_returns_revoked_source_memories(_no_embeddings, settings, expected):
    from app.services.agent_memory_service import search_department_memories

    db = _db()
    db.rpc_rows = _rpc_rows()
    out = search_department_memories(settings, db, ORG, "dept-1", query="renewal", top_k=10)
    assert [r["id"] for r in out] == expected


@pytest.mark.parametrize("settings, expected", [(OFF, 6), (ON, 2)])
def test_workspace_recall_never_returns_revoked_source_memories(settings, expected):
    from app.services.workspace_memory_service import recall_workspace

    db = _db()
    out = recall_workspace(db, org_id=ORG, query="from", top_k=10, settings=settings)
    assert len(out) == expected
    if settings is ON:
        assert sorted(r["id"] for r in out) == ["m-legacy", "m-live"]


@pytest.mark.parametrize("settings, expected", [(OFF, 6), (ON, 2)])
def test_hybrid_recall_never_returns_revoked_source_memories(settings, expected):
    from app.services.hybrid_memory_service import HybridMemoryService

    db = _db()
    svc = HybridMemoryService(settings)
    out = asyncio.run(svc._query_agent_memories(ORG, None, "from", 10, db))
    assert len(out) == expected
    columns = next(c for t, c, _i in db.reads if t == "agent_memories")
    assert ("source_connector_id" in columns) is (settings is ON)


# ---------------------------------------------------------------- observations


ACME = "eeeeeeee-0000-4000-8000-000000000001"
GLOBEX = "eeeeeeee-0000-4000-8000-000000000002"


def _observations() -> list[dict[str, Any]]:
    return [
        {"entity_id": ACME, "dimension": "sentiment", "evidence_quote": "live quote", "source_connector_id": LIVE},
        {"entity_id": ACME, "dimension": "sentiment", "evidence_quote": "revoked quote", "source_connector_id": DELETED},
        {"entity_id": GLOBEX, "dimension": "sentiment", "evidence_quote": "only revoked", "source_connector_id": REVOKED},
        {"entity_id": GLOBEX, "dimension": "urgency", "evidence_quote": "also revoked", "source_connector_id": DELETED},
    ]


def _signals() -> list[dict[str, Any]]:
    return [
        {"entity_id": ACME, "signal": "contact_gap_days", "value": 3},
        {"entity_id": GLOBEX, "signal": "contact_gap_days", "value": 30},
    ]


def test_observations_from_revoked_connectors_and_signals_built_only_on_them_are_dropped():
    db = _db()
    obs, sig = msl.drop_observations_from_revoked_sources(db, ORG, _observations(), _signals(), settings=ON)
    assert [o["evidence_quote"] for o in obs] == ["live quote"]
    # Acme keeps its signals (a live observation remains); Globex's rested only on revoked ones.
    assert [s["entity_id"] for s in sig] == [ACME]


def test_untagged_observations_and_their_signals_are_kept():
    db = _db()
    obs = [{"entity_id": ACME, "evidence_quote": "legacy", "source_connector_id": None}]
    out_obs, out_sig = msl.drop_observations_from_revoked_sources(db, ORG, obs, _signals(), settings=ON)
    assert out_obs == obs and out_sig == _signals()
    assert db.reads == []


def test_observation_filter_fails_closed():
    db = _db()
    db.fail_on = "connectors"
    legacy = {"entity_id": ACME, "evidence_quote": "legacy", "source_connector_id": None}
    obs, sig = msl.drop_observations_from_revoked_sources(db, ORG, [*_observations(), legacy], _signals(), settings=ON)
    assert obs == [legacy] and sig == []


def test_observation_filter_off_is_identity_and_columns_unchanged():
    db = _db()
    obs, sig = msl.drop_observations_from_revoked_sources(db, ORG, _observations(), _signals(), settings=OFF)
    assert obs == _observations() and sig == _signals() and db.reads == []
    assert msl.observation_columns("a, b", OFF) == "a, b"
    assert msl.observation_columns("a, b", ON) == "a, b, source_connector_id"


def _card_db() -> _DB:
    single = [{k: v for k, v in o.items()} | {"observed_at": "2026-10-10T00:00:00+00:00", "status": "active",
              "label": "negative", "score": -0.6, "source_system": "hubspot", "source_record_id": "r1"}
              for o in _observations()]
    return _DB(
        {
            "org_business_entities": [{"id": GLOBEX, "org_id": ORG, "display_name": "Globex", "kind": "company"}],
            "org_business_entity_bindings": [{"org_id": ORG, "entity_id": GLOBEX, "system": "hubspot"}],
            "entity_observations": [dict(o, org_id=ORG) for o in single],
            "entity_behavior_signals": [dict(s, org_id=ORG, window_end="2026-10-11") for s in _signals()],
            "connectors": [dict(c) for c in CONNECTORS],
        }
    )


@pytest.mark.parametrize("lineage", [False, True])
def test_account_card_never_quotes_a_revoked_source(lineage):
    from app.services import entity_context_card as card

    card.clear_cache_for_tests()
    settings = SimpleNamespace(entity_context_cards_enabled=True, memory_source_lineage_enabled=lineage)
    block, meta = card.build_entity_context_block(_card_db(), ORG, "how is Globex doing", spoken=False, settings=settings)
    assert meta.get("accounts") == [GLOBEX]
    if lineage:
        assert "only revoked" not in block and "also revoked" not in block
        assert "30 days ago" not in block  # the signal built only on revoked observations
    else:
        # Flag off: today's behaviour (the revoked observation is still quoted).
        assert "only revoked" in block or "also revoked" in block or "30 days ago" in block


@pytest.mark.parametrize("lineage", [False, True])
def test_account_health_reads_drop_revoked_sources(monkeypatch, lineage):
    from app.services import account_health as ah

    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        ah,
        "build_account_health",
        lambda entity, observations, signals, work, **kw: seen.update(obs=observations, sig=signals) or {},
    )
    db = _card_db()
    db.tables["work_objects"] = []
    ah.load_account_health(db, ORG, {"id": GLOBEX, "display_name": "Globex"}, settings=SimpleNamespace(memory_source_lineage_enabled=lineage))
    quotes = sorted(o["evidence_quote"] for o in seen["obs"])
    if lineage:
        assert quotes == [] and seen["sig"] == []
    else:
        assert quotes == ["also revoked", "only revoked"] and len(seen["sig"]) == 1
    obs_columns = next(c for t, c, _i in db.reads if t == "entity_observations")
    assert ("source_connector_id" in obs_columns) is lineage


@pytest.mark.parametrize("lineage", [False, True])
def test_account_health_batch_drops_revoked_sources(monkeypatch, lineage):
    from app.services import account_health as ah

    seen: list[tuple[str, list, list]] = []
    monkeypatch.setattr(
        ah,
        "build_account_health",
        lambda entity, observations, signals, work, **kw: seen.append((entity["id"], observations, signals)) or {},
    )
    db = _card_db()
    db.tables["work_objects"] = []
    db.tables["org_business_entities"].append({"id": ACME, "org_id": ORG, "display_name": "Acme"})
    ah.load_health_batch(db, ORG, settings=SimpleNamespace(memory_source_lineage_enabled=lineage))
    by = {eid: ([o["evidence_quote"] for o in obs], len(sig)) for eid, obs, sig in seen}
    if lineage:
        assert by[ACME] == (["live quote"], 1)
        assert by.get(GLOBEX, ([], 0)) == ([], 0)
    else:
        assert by[ACME] == (["live quote", "revoked quote"], 1)
        assert by[GLOBEX] == (["only revoked", "also revoked"], 1)


# ---------------------------------------------------------------- cache invalidation


@pytest.fixture
def _fresh_cache(monkeypatch):
    from app.services import cache_service

    monkeypatch.setattr(cache_service, "_MEMORY", {})
    monkeypatch.setattr(cache_service, "_cache", cache_service.CacheService(SimpleNamespace(redis_url=None)))
    monkeypatch.setattr(cache_service, "get_redis_client", lambda *_a, **_k: None, raising=False)
    cache_service._cache._redis = None
    yield cache_service


def test_epoch_is_absent_with_flag_off_and_invalidation_is_a_no_op(_fresh_cache):
    assert msl.epoch_parts(ORG, OFF) == ()
    assert msl.invalidate_org_derived_context(ORG, settings=OFF) is False
    assert msl.epoch_parts(ORG, ON) == ()  # never bumped
    assert _fresh_cache._MEMORY == {}


def test_revoke_changes_the_retrieval_and_instant_answer_cache_keys(_fresh_cache):
    from app.services.rag_cache_helpers import retrieval_cache_parts

    base = retrieval_cache_parts(ORG, "renewal terms", "organization", 8, {})
    before = base + msl.epoch_parts(ORG, ON)
    assert before == base
    assert msl.invalidate_org_derived_context(ORG, settings=ON, reason="test") is True
    after = base + msl.epoch_parts(ORG, ON)
    assert after != before and after[: len(base)] == base
    # Another org is untouched.
    assert msl.epoch_parts(OTHER_ORG, ON) == ()


def test_tier0_answer_cached_before_a_revoke_is_not_served(_fresh_cache, monkeypatch):
    from app.services import tier0_cache

    monkeypatch.setattr(tier0_cache, "get_cache_service", lambda settings=None: _fresh_cache._cache)
    asyncio.run(
        tier0_cache.set_tier0_answer(ON, org_id=ORG, query="what is our renewal date", answer="Nov 1", source_document_ids=[])
    )
    assert asyncio.run(tier0_cache.get_tier0_answer(ON, org_id=ORG, query="what is our renewal date"))["answer"] == "Nov 1"
    msl.invalidate_org_derived_context(ORG, settings=ON)
    assert asyncio.run(tier0_cache.get_tier0_answer(ON, org_id=ORG, query="what is our renewal date")) is None


def test_tier0_flag_off_keeps_serving(_fresh_cache, monkeypatch):
    from app.services import tier0_cache

    monkeypatch.setattr(tier0_cache, "get_cache_service", lambda settings=None: _fresh_cache._cache)
    asyncio.run(
        tier0_cache.set_tier0_answer(OFF, org_id=ORG, query="what is our renewal date", answer="Nov 1", source_document_ids=[])
    )
    msl.invalidate_org_derived_context(ORG, settings=OFF)
    assert asyncio.run(tier0_cache.get_tier0_answer(OFF, org_id=ORG, query="what is our renewal date"))["answer"] == "Nov 1"


def test_connector_read_results_are_dropped_for_the_org_only(_fresh_cache, monkeypatch):
    from app.services import read_action_result_cache as rc

    monkeypatch.setattr(msl, "lineage_required", lambda settings=None: True)
    rc.clear_read_action_result_cache()
    rc.set_cached_read_result(ORG, "hubspot.contacts.list", {"q": "acme"}, {"rows": [1]})
    rc.set_cached_read_result(OTHER_ORG, "hubspot.contacts.list", {"q": "acme"}, {"rows": [2]})
    msl.invalidate_org_derived_context(ORG, settings=ON)
    assert rc.get_cached_read_result(ORG, "hubspot.contacts.list", {"q": "acme"}) is None
    assert rc.get_cached_read_result(OTHER_ORG, "hubspot.contacts.list", {"q": "acme"}) == {"rows": [2]}


def test_connector_read_result_cached_on_another_replica_misses_after_the_epoch(_fresh_cache, monkeypatch):
    """The in-process clear runs on one replica; the epoch (Redis) reaches the others."""
    from app.services import read_action_result_cache as rc

    monkeypatch.setattr(msl, "lineage_required", lambda settings=None: True)
    rc.clear_read_action_result_cache()
    rc.set_cached_read_result(ORG, "hubspot.deals.list", {}, {"rows": [1]})
    # Simulate a bump made by another process: only the shared epoch changes.
    _fresh_cache._cache.set_sync(msl.EPOCH_NAMESPACE, f"{__import__('time').time() + 1:.6f}", 60, ORG)
    assert rc.get_cached_read_result(ORG, "hubspot.deals.list", {}) is None


def test_read_cache_unchanged_with_flag_off(monkeypatch):
    from app.services import read_action_result_cache as rc

    monkeypatch.setattr(msl, "lineage_required", lambda settings=None: False)
    rc.clear_read_action_result_cache()
    rc.set_cached_read_result(ORG, "hubspot.deals.list", {}, {"rows": [1]})
    assert rc.get_cached_read_result(ORG, "hubspot.deals.list", {}) == {"rows": [1]}


def test_invalidation_clears_in_process_org_caches(_fresh_cache, monkeypatch):
    from app.services import connector_snapshot_cache as snap
    from app.services import entity_context_card as card
    from app.services.org_context_service import get_org_context_service

    snap.set_cached_connected(ORG, ["hubspot"])
    snap.set_cached_connected(OTHER_ORG, ["hubspot"])
    card._name_cache[ORG] = (0.0, [])
    service = get_org_context_service()
    service._cache[f"{ORG}:production:standard"] = object()
    service._cache[f"{ORG}:staging:standard"] = object()
    service._cache[f"{OTHER_ORG}:production:standard"] = object()
    msl.invalidate_org_derived_context(ORG, settings=ON)
    assert snap.get_cached_connected(ORG) is None
    assert snap.get_cached_connected(OTHER_ORG) == ["hubspot"]
    assert ORG not in card._name_cache
    assert not any(k.startswith(f"{ORG}:") for k in service._cache)
    assert f"{OTHER_ORG}:production:standard" in service._cache
    service._cache.pop(f"{OTHER_ORG}:production:standard", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("lineage", [False, True])
async def test_connector_delete_route_invalidates_before_provider_revoke(monkeypatch, lineage):
    import json  # noqa: F401
    from uuid import UUID

    from app.routers import connectors as routes
    from app.routers.connectors import ConnectorDeleteRequest, _delete_connector_impl
    from app.services import source_lifecycle as sl
    from tests.routers.test_managed_connector_flow import Query, row

    cid = UUID(DELETED)
    store = [row(id=str(cid), org_id=ORG, config={}, vendor="hubspot", type="hubspot")]
    client = SimpleNamespace(table=lambda name: Query(store if name == "connectors" else []))
    order: list[str] = []
    monkeypatch.setattr(routes, "create_client", lambda *a: client)
    monkeypatch.setattr(routes, "write_audit_event", lambda *a, **kw: None)
    real = msl.invalidate_org_derived_context
    monkeypatch.setattr(
        msl,
        "invalidate_org_derived_context",
        lambda org_id, settings=None, reason="": order.append(f"invalidate:{reason}:{real(org_id, settings=settings, reason=reason)}"),
    )
    from app.connectors import provider_revoke as pr

    monkeypatch.setattr(sl, "revoke_on_disconnect", lambda *a, **k: order.append("revoke") or pr.RevokeOutcome("revoked", "hubspot"))
    monkeypatch.setattr("app.connectors.platform.clear_connector_oauth_tokens", lambda *a: None)
    monkeypatch.setattr(msl, "_clear_in_process", lambda org_id: None)
    settings = SimpleNamespace(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service",
        memory_source_lineage_enabled=lineage,
    )
    out = await _delete_connector_impl(cid, ConnectorDeleteRequest(confirmName="desk"), ({"user_id": "u1"}, ORG), settings)
    assert out == {"success": True}
    assert order == [f"invalidate:connector.deleted:{lineage}", "revoke"]


# ---------------------------------------------------------------- workflow outcome memory


def test_workflow_outcome_memory_drops_provider_error_text_with_lineage_on():
    """An untagged outcome memory cannot be purged by source, so with lineage on it keeps
    the error count, not the provider's text. Off: unchanged."""
    from app.workflows.execution_engine_runtime import _outcome_memory_insight

    errors = ["HubSpot 400: contact jane@acme.com is archived", "b", "c", "d"]
    assert _outcome_memory_insight("r1", "failed", errors, OFF) == (
        "Run r1 finished with status failed. Errors: HubSpot 400: contact jane@acme.com is archived; b; c"
    )
    assert _outcome_memory_insight("r1", "failed", errors, ON) == (
        "Run r1 finished with status failed. 4 step error(s); details are on the run."
    )
    assert _outcome_memory_insight("r1", "completed", [], ON) == "Run r1 finished with status completed."


# ---------------------------------------------------------------- context engine account inputs


@pytest.mark.parametrize("lineage", [False, True])
def test_context_engine_drops_a_revoked_connection_even_while_the_vendor_is_live(lineage):
    """Vendor-level governance keeps HubSpot observations while any HubSpot connection is
    live. Per-connector lineage also drops those learned through a revoked connection."""
    import copy

    from app.services import account_context_sources as acs
    from app.services.entity_context_card import clear_cache_for_tests
    from tests.context_engine.harness import ORG_A, TABLES, FakeClient

    clear_cache_for_tests()
    hs_live, hs_old = LIVE, DELETED
    tables = copy.deepcopy(TABLES)
    tables["connectors"] = [
        {"id": hs_live, "org_id": ORG_A, "type": "hubspot", "vendor": "hubspot", "status": "active", "deleted_at": None},
        {"id": hs_old, "org_id": ORG_A, "type": "hubspot", "vendor": "hubspot", "status": "disconnected",
         "deleted_at": "2026-10-12T10:00:00+00:00"},
    ]
    for row in tables["entity_observations"]:
        row["source_connector_id"] = hs_live
    old = dict(tables["entity_observations"][0], id="obs-a-old", source_connector_id=hs_old,
               evidence_quote="OLD-PORTAL-QUOTE we will not renew")
    tables["entity_observations"].insert(0, old)
    settings = SimpleNamespace(
        context_engine_observations_v1=True,
        context_engine_account_signals_v1=True,
        retrieved_content_guard_enabled=True,
        memory_source_lineage_enabled=lineage,
    )
    sources, _meta = acs.build_account_context_sources(
        FakeClient(tables), ORG_A, "How is Acme Corp doing?", spoken=False, settings=settings
    )
    text = "\n".join(s.content for s in sources)
    assert ("OLD-PORTAL-QUOTE" in text) is (not lineage)
    assert any(s.source_type == "account_measurement" for s in sources)  # live observations remain
    clear_cache_for_tests()
