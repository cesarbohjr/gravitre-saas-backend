"""Phase 2A relay behaviour with a fake RPC client (the SQL is covered in tests/db)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import domain_events as de


class _Rpc:
    def __init__(self, client: _FakeClient, name: str, params: dict[str, Any]) -> None:
        self._client = client
        self._name = name
        self._params = params

    def execute(self):
        self._client.calls.append((self._name, self._params))
        return SimpleNamespace(data=self._client.respond(self._name, self._params))


class _FakeClient:
    def __init__(self, events: list[dict[str, Any]], *, complete_ok: bool = True) -> None:
        self.events = events
        self.complete_ok = complete_ok
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.upserts: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.fail_status = "pending"

    def rpc(self, name: str, params: dict[str, Any]):
        return _Rpc(self, name, params)

    def respond(self, name: str, params: dict[str, Any]):
        if name == "claim_domain_events":
            out, self.events = self.events, []
            return out
        if name == "complete_domain_event":
            return self.complete_ok
        if name == "fail_domain_event":
            return self.fail_status
        if name == "domain_event_outbox_stats":
            return {"pending": 0}
        if name == "prune_domain_events":
            return 3
        raise AssertionError(name)

    def table(self, name: str):
        client = self

        class _T:
            def upsert(self, row, **kwargs):
                client.upserts.append((row, kwargs))
                return SimpleNamespace(execute=lambda: SimpleNamespace(data=[row]))

        assert name == de.OUTBOX_TABLE
        return _T()

    def settled(self, name: str) -> list[dict[str, Any]]:
        return [p for n, p in self.calls if n == name]


def _event(**kw) -> dict[str, Any]:
    base = {
        "id": 7,
        "event_id": "e-7",
        "event_type": de.EVENT_EXECUTION_OUTCOME_FINALIZED,
        "aggregate_id": "run-1",
        "attempts": 1,
        "delivered_handlers": [],
        "payload": {"run_id": "run-1", "status": "completed"},
    }
    base.update(kw)
    return base


@pytest.fixture(autouse=True)
def _reset():
    de.reset_domain_event_handlers_for_tests()
    yield
    de.reset_domain_event_handlers_for_tests()


def test_claims_with_worker_lease_and_batch():
    client = _FakeClient([])
    relay = de.DomainEventRelay(client, worker_id="w1", batch_size=20, lease_seconds=90)
    relay.run_once()
    assert client.calls[0] == ("claim_domain_events", {"p_worker": "w1", "p_limit": 20, "p_lease_seconds": 90})


def test_runs_handlers_then_completes_with_their_names():
    seen: list[str] = []
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "a", lambda c, e: seen.append("a"))
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "b", lambda c, e: seen.append("b"))
    client = _FakeClient([_event()])
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert seen == ["a", "b"]
    assert result.delivered == 1 and result.claimed == 1
    assert client.settled("complete_domain_event") == [
        {"p_id": 7, "p_worker": "w1", "p_delivered_handlers": ["a", "b"]}
    ]


def test_event_without_handlers_is_completed():
    client = _FakeClient([_event(event_type="source.disconnected")])
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert result.delivered == 1
    assert client.settled("complete_domain_event")[0]["p_delivered_handlers"] == []


def test_failing_handler_retries_with_backoff_and_keeps_successes():
    def boom(c, e):
        raise RuntimeError("downstream 503")

    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "ok", lambda c, e: None)
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "boom", boom)
    client = _FakeClient([_event(attempts=3)])
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert result.retried == 1 and result.delivered == 0
    (fail,) = client.settled("fail_domain_event")
    assert fail["p_delivered_handlers"] == ["ok"]
    assert "boom: RuntimeError: downstream 503" in fail["p_error"]
    assert fail["p_retry_seconds"] == de.retry_delay_seconds(3) == 60
    assert client.settled("complete_domain_event") == []


def test_retry_skips_handlers_that_already_succeeded():
    calls: list[str] = []
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "ok", lambda c, e: calls.append("ok"))
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "late", lambda c, e: calls.append("late"))
    client = _FakeClient([_event(attempts=2, delivered_handlers=["ok"])])
    de.DomainEventRelay(client, worker_id="w1").run_once()
    assert calls == ["late"]
    assert client.settled("complete_domain_event")[0]["p_delivered_handlers"] == ["ok", "late"]


def test_dead_letter_is_counted():
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "boom", lambda c, e: 1 / 0)
    client = _FakeClient([_event(attempts=10)])
    client.fail_status = "dead"
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert result.dead == 1 and result.retried == 0


def test_lost_lease_is_reported_not_counted_delivered():
    client = _FakeClient([_event()], complete_ok=False)
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert result.delivered == 0 and result.lease_lost == 1


def test_settle_error_leaves_event_for_lease_expiry():
    client = _FakeClient([_event()])

    def broken_rpc(name, params):
        if name == "complete_domain_event":
            raise ConnectionError("reset")
        return _Rpc(client, name, params)

    client.rpc = broken_rpc  # type: ignore[assignment]
    result = de.DomainEventRelay(client, worker_id="w1").run_once()
    assert result.delivered == 0 and result.errors and "reset" in result.errors[0]


def test_retry_backoff_is_exponential_and_capped():
    assert [de.retry_delay_seconds(a) for a in (1, 2, 3, 4)] == [15, 30, 60, 120]
    assert de.retry_delay_seconds(50) == de.RETRY_MAX_SECONDS


def test_duplicate_handler_name_rejected():
    de.register_domain_event_handler("x.y", "h", lambda c, e: None)
    with pytest.raises(ValueError):
        de.register_domain_event_handler("x.y", "h", lambda c, e: None)


def test_enqueue_is_idempotent_upsert_and_never_raises():
    client = _FakeClient([])
    assert de.enqueue_domain_event(
        client,
        org_id="o1",
        event_type="source.sync_completed",
        aggregate_type="connector",
        aggregate_id="c1",
        idempotency_key="c1:2026-10-11",
        payload={"n": 1},
    )
    row, kwargs = client.upserts[0]
    assert kwargs == {"on_conflict": "event_type,idempotency_key", "ignore_duplicates": True}
    assert row["criticality"] == "best_effort" and row["payload"] == {"n": 1}

    class _Broken:
        def table(self, name):
            raise RuntimeError("relation does not exist")

    assert de.enqueue_domain_event(
        _Broken(), org_id="o", event_type="a.b", aggregate_type="t", aggregate_id="1", idempotency_key="k"
    ) is False


def test_stats_and_prune_helpers():
    client = _FakeClient([])
    assert de.domain_event_outbox_stats(client) == {"pending": 0}
    assert de.prune_domain_events(client, retention_days=7) == 3
    assert ("prune_domain_events", {"p_retention_days": 7, "p_batch": 5000}) in client.calls


def test_relay_scheduler_is_off_by_default(monkeypatch):
    from app.config import get_settings
    from app.schedulers import domain_event_relay_scheduler as sched

    assert get_settings().domain_event_relay_enabled is False
    assert sched.start_domain_event_relay_scheduler() is None


@pytest.mark.asyncio
async def test_relay_scheduler_starts_when_enabled(monkeypatch):
    from app.schedulers import domain_event_relay_scheduler as sched

    settings = SimpleNamespace(
        domain_event_relay_enabled=True,
        domain_event_relay_interval_seconds=15,
        domain_event_relay_batch_size=50,
        domain_event_relay_lease_seconds=120,
        domain_event_retention_days=14,
    )
    monkeypatch.setattr(sched, "get_settings", lambda: settings)

    async def fake_loop(s, interval):
        return interval

    monkeypatch.setattr(sched, "_loop", fake_loop)
    task = sched.start_domain_event_relay_scheduler()
    assert task is not None
    assert await task == 15


def test_internal_stats_endpoint_requires_secret(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import Settings, get_settings
    from app.main import app
    from app.routers import ops_internal

    base = get_settings()
    settings = base.model_copy(update={"internal_api_secret": "s3cret"})
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(ops_internal, "get_supabase_client", lambda s: _FakeClient([]))
    try:
        c = TestClient(app)
        assert c.get("/api/internal/ops/domain-events").status_code == 401
        r = c.get("/api/internal/ops/domain-events", headers={"X-Internal-Secret": "s3cret"})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "relay_enabled": False, "stats": {"pending": 0}}
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert isinstance(settings, Settings)
