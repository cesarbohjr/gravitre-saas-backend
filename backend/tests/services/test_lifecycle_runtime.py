"""New ingestion needs runtime evidence of lifecycle enforcement, not only configuration.

Every case sets the configuration prerequisites and every new-ingestion flag on, then
varies the runtime state of this process: relay task, heartbeat, purge handler,
database probe. Anything short of all-good keeps ingestion off (fail closed).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from postgrest.exceptions import APIError

from app.schedulers import domain_event_relay_scheduler as relay_sched
from app.schedulers import entity_behavior_signals_scheduler as signals
from app.schedulers import rag_ingest_pilot_scheduler as pilot
from app.services import (
    domain_events,
    entity_observations,
    entity_writer,
    lifecycle_runtime,
)
from app.services.ingestion_interlock import (
    INGESTION_FLAGS,
    LIFECYCLE_PREREQUISITES,
    IngestionHeldError,
    ensure_existing_ingestion_allowed,
    existing_ingestion_hold_reason,
    ingestion_flag_configured,
    ingestion_flag_on,
    ingestion_interlock_report,
    lifecycle_blockers,
)
from app.services.lifecycle_runtime import (
    PURGE_RPC_SENTINEL,
    probe_lifecycle_database,
    record_db_probe,
    runtime_lifecycle_blockers,
)

CONFIGURED = SimpleNamespace(**dict(LIFECYCLE_PREREQUISITES), **{f: True for f in INGESTION_FLAGS})
GATED_CONFIGURED = SimpleNamespace(existing_ingestion_requires_lifecycle=True, **dict(LIFECYCLE_PREREQUISITES))


def _new_ingestion_effective() -> dict[str, bool]:
    out = {f: ingestion_flag_on(CONFIGURED, f) for f in INGESTION_FLAGS}
    out["writer_enabled"] = entity_writer.writer_enabled(CONFIGURED)
    out["observations_enabled"] = entity_observations.observations_enabled(CONFIGURED)
    return out


def _assert_all_held() -> None:
    assert not any(_new_ingestion_effective().values())
    assert all(ingestion_flag_configured(CONFIGURED, f) for f in INGESTION_FLAGS)


# ------------------------------------------------------------------ runtime states


def test_configuration_alone_is_not_enough():
    blockers = runtime_lifecycle_blockers()
    assert "relay_not_running" in blockers
    assert "relay_no_successful_tick" in blockers
    assert "handler_missing:source.disconnected:source_lifecycle.purge_derived_data" in blockers
    assert "db_probe_missing" in blockers
    _assert_all_held()
    assert lifecycle_blockers(CONFIGURED) == [f"runtime:{b}" for b in blockers]


def test_all_good_lets_new_ingestion_through(lifecycle_runtime_ready):
    assert runtime_lifecycle_blockers() == []
    assert all(_new_ingestion_effective().values())
    report = ingestion_interlock_report(CONFIGURED)
    assert report["lifecycle_ready"] is True and report["runtime"]["ready"] is True
    assert report["runtime"]["relay_task"] == "running"
    assert all(v == {"requested": True, "effective": True} for v in report["new_ingestion"].values())


def test_relay_task_exited(lifecycle_runtime_ready):
    lifecycle_runtime_ready.finished = True
    assert "relay_task_exited" in runtime_lifecycle_blockers()
    _assert_all_held()
    assert ingestion_interlock_report(CONFIGURED)["runtime"]["relay_task"] == "exited"


def test_relay_stopped(lifecycle_runtime_ready):
    lifecycle_runtime.relay_stopped()
    assert {"relay_not_running", "relay_no_successful_tick", "db_probe_missing"} <= set(runtime_lifecycle_blockers())
    _assert_all_held()


def test_relay_heartbeat_stale(lifecycle_runtime_ready, monkeypatch):
    base = lifecycle_runtime._now()
    window = lifecycle_runtime.heartbeat_window_s()
    monkeypatch.setattr(lifecycle_runtime, "_now", lambda: base + window - 1)
    assert not any(b.startswith("relay_heartbeat_stale") for b in runtime_lifecycle_blockers())
    monkeypatch.setattr(lifecycle_runtime, "_now", lambda: base + window + 5)
    assert any(b.startswith("relay_heartbeat_stale") for b in runtime_lifecycle_blockers())
    _assert_all_held()


def test_failing_ticks_do_not_refresh_the_heartbeat(lifecycle_runtime_ready, monkeypatch):
    base = lifecycle_runtime._now()
    later = base + lifecycle_runtime.heartbeat_window_s() + 5
    monkeypatch.setattr(lifecycle_runtime, "_now", lambda: later)
    for _ in range(3):
        lifecycle_runtime.record_relay_tick(ok=False, error="claim_domain_events: boom")
    assert any(b.startswith("relay_heartbeat_stale") for b in runtime_lifecycle_blockers())
    status = lifecycle_runtime.runtime_lifecycle_status()
    assert status["consecutive_tick_failures"] == 3 and "boom" in status["last_tick_error"]
    _assert_all_held()


def test_purge_handler_missing(lifecycle_runtime_ready):
    domain_events.reset_domain_event_handlers_for_tests()
    assert runtime_lifecycle_blockers() == [
        "handler_missing:source.disconnected:source_lifecycle.purge_derived_data"
    ]
    _assert_all_held()


def test_purge_rpc_missing(lifecycle_runtime_ready):
    record_db_probe(probe_lifecycle_database(_ProbeClient(rpc_error=_missing_function())))
    assert runtime_lifecycle_blockers() == ["purge_rpc_unavailable:PGRST202"]
    _assert_all_held()


def test_db_probe_failed_or_stale(lifecycle_runtime_ready, monkeypatch):
    record_db_probe({"ok": False, "blockers": ["purge_dead_lettered"]})
    assert runtime_lifecycle_blockers() == ["purge_dead_lettered"]
    _assert_all_held()

    record_db_probe({"ok": True, "blockers": []})
    lifecycle_runtime.record_relay_tick(ok=True)
    base = lifecycle_runtime._now()
    monkeypatch.setattr(lifecycle_runtime, "_now", lambda: base + lifecycle_runtime.DB_PROBE_MAX_AGE_S + 1)
    # Keep the heartbeat fresh so only the probe age is at fault.
    lifecycle_runtime._state.last_ok_tick_at = base + lifecycle_runtime.DB_PROBE_MAX_AGE_S
    assert [b for b in runtime_lifecycle_blockers() if b.startswith("db_probe_stale")]
    _assert_all_held()


def test_probe_result_without_ok_true_fails_closed(lifecycle_runtime_ready):
    record_db_probe({})
    assert runtime_lifecycle_blockers() == ["db_probe_failed"]
    _assert_all_held()


# ------------------------------------------------------------------ fail closed


def test_error_reading_runtime_state_fails_closed(lifecycle_runtime_ready, monkeypatch):
    def boom() -> list[str]:
        raise RuntimeError("state corrupted")

    monkeypatch.setattr(lifecycle_runtime, "_blockers", boom)
    assert runtime_lifecycle_blockers() == ["runtime_state_unknown"]
    _assert_all_held()


def test_runtime_module_failure_fails_closed(lifecycle_runtime_ready, monkeypatch):
    def boom() -> list[str]:
        raise ImportError("lifecycle_runtime unavailable")

    monkeypatch.setattr(lifecycle_runtime, "runtime_lifecycle_blockers", boom)
    _assert_all_held()


def test_task_without_done_counts_as_exited(lifecycle_runtime_ready):
    lifecycle_runtime.relay_started(object(), interval_s=15)
    lifecycle_runtime.record_relay_tick(ok=True)
    record_db_probe({"ok": True, "blockers": []})
    assert runtime_lifecycle_blockers() == ["relay_task_exited"]


# ------------------------------------------------------------------ existing ingestion (owner switch)


def test_owner_switch_on_with_configuration_but_no_runtime_holds_existing_syncs():
    reason = existing_ingestion_hold_reason(GATED_CONFIGURED, "hubspot")
    assert reason is not None and reason.startswith("lifecycle_runtime_not_ready:")
    with pytest.raises(IngestionHeldError):
        ensure_existing_ingestion_allowed(GATED_CONFIGURED, "hubspot")
    report = ingestion_interlock_report(GATED_CONFIGURED)
    assert report["existing_ingestion"]["standalone_worker"] == "held"
    assert report["existing_ingestion"]["knowledge_sync"]["hubspot"].startswith("held:lifecycle_runtime_not_ready")


def test_owner_switch_off_ignores_runtime_state():
    # Default: existing ingestion runs as before whatever the runtime state.
    off = SimpleNamespace(existing_ingestion_requires_lifecycle=False, **dict(LIFECYCLE_PREREQUISITES))
    assert existing_ingestion_hold_reason(off, "notion") is None
    ensure_existing_ingestion_allowed(off, "notion")


def test_owner_switch_on_with_runtime_ready(lifecycle_runtime_ready):
    assert existing_ingestion_hold_reason(GATED_CONFIGURED, "hubspot") is None
    assert existing_ingestion_hold_reason(GATED_CONFIGURED, "notion") == "provider_revoke_not_supported:notion"


# ------------------------------------------------------------------ database probe


class _ProbeQuery:
    def __init__(self, client: _ProbeClient, table: str) -> None:
        self.client = client
        self.table = table
        self.filters: list[tuple[str, Any]] = []

    def select(self, cols: str) -> _ProbeQuery:
        self.client.ops.append(("select", self.table, cols))
        return self

    def eq(self, col: str, val: Any) -> _ProbeQuery:
        self.filters.append(("eq", (col, val)))
        return self

    def in_(self, col: str, vals: list[str]) -> _ProbeQuery:
        self.filters.append(("in", (col, tuple(vals))))
        return self

    def lt(self, col: str, val: Any) -> _ProbeQuery:
        self.filters.append(("lt", (col, val)))
        return self

    def limit(self, n: int) -> _ProbeQuery:
        return self

    def execute(self) -> SimpleNamespace:
        if self.client.table_error:
            raise self.client.table_error
        eqs = dict(v for k, v in self.filters if k == "eq")
        if eqs.get("status") == "dead":
            return SimpleNamespace(data=[{"id": 1}] if self.client.dead else [])
        return SimpleNamespace(data=[{"id": 2}] if self.client.lagging else [])


class _ProbeClient:
    def __init__(self, *, rpc_error: Exception | None = None, dead=False, lagging=False, table_error=None):
        self.rpc_error = rpc_error
        self.dead = dead
        self.lagging = lagging
        self.table_error = table_error
        self.ops: list[tuple] = []

    def rpc(self, name: str, params: dict[str, Any]) -> SimpleNamespace:
        self.ops.append(("rpc", name, dict(params)))

        def execute() -> SimpleNamespace:
            if self.rpc_error:
                raise self.rpc_error
            return SimpleNamespace(data={"rag_sources": 0})

        return SimpleNamespace(execute=execute)

    def table(self, name: str) -> _ProbeQuery:
        return _ProbeQuery(self, name)


def _sentinel() -> APIError:
    return APIError(
        {"code": "P0001", "message": f"purge_connector_derived_data: {PURGE_RPC_SENTINEL}", "hint": None, "details": None}
    )


def _missing_function() -> APIError:
    return APIError(
        {
            "code": "PGRST202",
            "message": "Could not find the function public.purge_connector_derived_data in the schema cache",
            "hint": None,
            "details": None,
        }
    )


def test_probe_passes_and_is_read_only():
    client = _ProbeClient(rpc_error=_sentinel())
    result = probe_lifecycle_database(client)
    assert result == {
        "ok": True,
        "blockers": [],
        "checks": {"purge_rpc": "present", "purge_dead_letters": 0, "purge_lagging": 0},
    }
    rpc = [op for op in client.ops if op[0] == "rpc"]
    assert rpc == [
        (
            "rpc",
            "purge_connector_derived_data",
            {
                "p_org_id": None,
                "p_connector_id": None,
                "p_vendor": None,
                "p_disconnected_at": None,
                "p_dry_run": True,
                "p_event_id": None,
            },
        )
    ]
    assert {op[0] for op in client.ops} == {"rpc", "select"}


@pytest.mark.parametrize(
    "client, blocker",
    [
        (lambda: _ProbeClient(rpc_error=_missing_function()), "purge_rpc_unavailable:PGRST202"),
        (lambda: _ProbeClient(rpc_error=RuntimeError("connection refused")), "purge_rpc_unavailable:RuntimeError"),
        (lambda: _ProbeClient(rpc_error=None), "purge_rpc_unverified"),
        (lambda: _ProbeClient(rpc_error=_sentinel(), dead=True), "purge_dead_lettered"),
        (lambda: _ProbeClient(rpc_error=_sentinel(), lagging=True), "purge_lagging"),
        (lambda: _ProbeClient(rpc_error=_sentinel(), table_error=RuntimeError("down")), "outbox_unreadable"),
    ],
)
def test_probe_failures_block(client, blocker):
    result = probe_lifecycle_database(client())
    assert result["ok"] is False
    assert blocker in result["blockers"]


# ------------------------------------------------------------------ relay loop feeds the evidence


class _FakeRelay:
    batch_size = 50
    worker_id = "w-test"
    fail = False

    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    def run_once(self) -> SimpleNamespace:
        if _FakeRelay.fail:
            raise RuntimeError("claim_domain_events failed")
        return SimpleNamespace(claimed=0, as_dict=dict)


async def _one_relay_iteration(monkeypatch, probe_client: _ProbeClient) -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        if len(sleeps) >= 2:  # initial delay, then the pause after the first tick
            raise asyncio.CancelledError

    monkeypatch.setattr(relay_sched, "shared_service_client", lambda *_a, **_k: probe_client)
    monkeypatch.setattr(relay_sched, "DomainEventRelay", _FakeRelay)
    monkeypatch.setattr(relay_sched, "domain_event_outbox_stats", lambda c: {})
    monkeypatch.setattr(relay_sched, "prune_domain_events", lambda c, **k: 0)
    monkeypatch.setattr(relay_sched.asyncio, "sleep", fake_sleep)
    settings = SimpleNamespace(
        domain_event_relay_batch_size=50, domain_event_relay_lease_seconds=120, domain_event_retention_days=14
    )
    with pytest.raises(asyncio.CancelledError):
        await relay_sched._loop(settings, 15)


async def test_relay_loop_heartbeat_and_probe_make_the_process_ready(monkeypatch):
    from app.services.source_lifecycle import register_source_lifecycle_handlers

    saved = {k: list(v) for k, v in domain_events._handlers.items()}
    try:
        register_source_lifecycle_handlers()
        alive = SimpleNamespace(done=lambda: False)
        lifecycle_runtime.relay_started(alive, interval_s=15, lease_s=120)
        assert "relay_no_successful_tick" in runtime_lifecycle_blockers()
        _FakeRelay.fail = False
        await _one_relay_iteration(monkeypatch, _ProbeClient(rpc_error=_sentinel()))
        assert runtime_lifecycle_blockers() == []
        assert ingestion_flag_on(CONFIGURED, "entity_writer_enabled")
    finally:
        domain_events._handlers.clear()
        domain_events._handlers.update(saved)


async def test_relay_loop_with_failing_tick_and_missing_rpc_stays_not_ready(monkeypatch):
    from app.services.source_lifecycle import register_source_lifecycle_handlers

    saved = {k: list(v) for k, v in domain_events._handlers.items()}
    try:
        register_source_lifecycle_handlers()
        lifecycle_runtime.relay_started(SimpleNamespace(done=lambda: False), interval_s=15, lease_s=120)
        _FakeRelay.fail = True
        await _one_relay_iteration(monkeypatch, _ProbeClient(rpc_error=_missing_function()))
        blockers = runtime_lifecycle_blockers()
        assert "relay_no_successful_tick" in blockers
        # The probe is skipped when the tick itself failed, so there is no evidence at all.
        assert "db_probe_missing" in blockers
        assert not ingestion_flag_on(CONFIGURED, "entity_writer_enabled")
    finally:
        _FakeRelay.fail = False
        domain_events._handlers.clear()
        domain_events._handlers.update(saved)


def test_relay_start_records_task_and_stop_clears_it(monkeypatch):
    monkeypatch.setattr(
        relay_sched,
        "get_settings",
        lambda: SimpleNamespace(
            domain_event_relay_enabled=True, domain_event_relay_interval_seconds=15, domain_event_relay_lease_seconds=120
        ),
    )
    alive = SimpleNamespace(done=lambda: False, cancel=lambda: None)

    def fake_task(coro):
        coro.close()
        return alive

    saved = {k: list(v) for k, v in domain_events._handlers.items()}
    monkeypatch.setattr(relay_sched.asyncio, "create_task", fake_task)
    try:
        assert relay_sched.start_domain_event_relay_scheduler() is alive
        blockers = runtime_lifecycle_blockers()
        assert "relay_not_running" not in blockers and "relay_task_exited" not in blockers
        assert not any(b.startswith("handler_missing") for b in blockers)
        # Started, but no tick and no probe yet: still not ready.
        assert {"relay_no_successful_tick", "db_probe_missing"} <= set(blockers)
        lifecycle_runtime.relay_stopped()
        assert "relay_not_running" in runtime_lifecycle_blockers()
    finally:
        domain_events._handlers.clear()
        domain_events._handlers.update(saved)


# ------------------------------------------------------------------ schedulers re-check every tick


def test_schedulers_start_on_configuration_alone(monkeypatch):
    settings = SimpleNamespace(
        **vars(CONFIGURED),
        rag_worker_pilot_org_ids="11111111-1111-4111-8111-111111111111",
        rag_worker_pilot_interval_seconds=30,
        entity_behavior_signals_interval_seconds=86400,
    )
    created: list[Any] = []

    def fake_task(coro):
        created.append(coro)
        coro.close()
        return "task"

    monkeypatch.setattr(pilot, "get_settings", lambda: settings)
    monkeypatch.setattr(signals, "get_settings", lambda: settings)
    monkeypatch.setattr(pilot.asyncio, "create_task", fake_task)
    monkeypatch.setattr(signals.asyncio, "create_task", fake_task)
    assert pilot.start_rag_ingest_pilot_scheduler() == "task"
    assert signals.start_entity_behavior_signals_scheduler() == "task"


async def _one_loop_iteration(monkeypatch, module, loop_fn, settings) -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        if len(sleeps) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(module, "shared_service_client", lambda *_a, **_k: object())
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await loop_fn(settings, 30)


async def test_pilot_tick_claims_nothing_without_runtime_evidence(monkeypatch):
    calls: list[Any] = []
    monkeypatch.setattr(pilot, "run_pilot_tick", lambda *a: calls.append(a) or {"processed": 0, "released": 0})
    settings = SimpleNamespace(**vars(CONFIGURED), disable_ingestion=False, rag_worker_pilot_org_ids="")
    await _one_loop_iteration(monkeypatch, pilot, pilot._loop, settings)
    assert calls == []


async def test_pilot_tick_runs_with_runtime_evidence(monkeypatch, lifecycle_runtime_ready):
    calls: list[Any] = []
    monkeypatch.setattr(pilot, "run_pilot_tick", lambda *a: calls.append(a) or {"processed": 0, "released": 0})
    settings = SimpleNamespace(**vars(CONFIGURED), disable_ingestion=False, rag_worker_pilot_org_ids="")
    await _one_loop_iteration(monkeypatch, pilot, pilot._loop, settings)
    assert len(calls) == 1


async def test_pilot_tick_respects_disable_ingestion(monkeypatch, lifecycle_runtime_ready):
    calls: list[Any] = []
    monkeypatch.setattr(pilot, "run_pilot_tick", lambda *a: calls.append(a) or {"processed": 0, "released": 0})
    settings = SimpleNamespace(**vars(CONFIGURED), disable_ingestion=True, rag_worker_pilot_org_ids="")
    await _one_loop_iteration(monkeypatch, pilot, pilot._loop, settings)
    assert calls == []


async def test_behavior_signals_tick_held_without_runtime_evidence(monkeypatch):
    calls: list[Any] = []
    monkeypatch.setattr(signals, "run_behavior_signals", lambda *a, **k: calls.append(a) or {})
    await _one_loop_iteration(monkeypatch, signals, signals._loop, CONFIGURED)
    assert calls == []


async def test_behavior_signals_tick_runs_with_runtime_evidence(monkeypatch, lifecycle_runtime_ready):
    calls: list[Any] = []
    monkeypatch.setattr(signals, "run_behavior_signals", lambda *a, **k: calls.append(a) or {})
    await _one_loop_iteration(monkeypatch, signals, signals._loop, CONFIGURED)
    assert len(calls) == 1


# ------------------------------------------------------------------ ops endpoint


def test_ops_endpoint_reports_runtime_state_behind_the_internal_secret(lifecycle_runtime_ready):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    settings = get_settings().model_copy(update={"internal_api_secret": "s3cret"})
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        c = TestClient(app)
        assert c.get("/api/internal/ops/ingestion-interlock").status_code == 401
        r = c.get("/api/internal/ops/ingestion-interlock", headers={"X-Internal-Secret": "s3cret"})
        assert r.status_code == 200
        body = r.json()
        assert body["runtime"]["ready"] is True and body["runtime"]["relay_task"] == "running"
        # Defaults: configuration prerequisites are off, so lifecycle is not ready overall.
        assert body["lifecycle_configured"] is False and body["lifecycle_ready"] is False
        assert body["existing_ingestion"]["requires_lifecycle"] is False
    finally:
        app.dependency_overrides.pop(get_settings, None)
