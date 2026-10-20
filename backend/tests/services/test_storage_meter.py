"""Storage meter, snapshots, usage API and the plan storage quota (warn/refuse only when on)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_admin,
)
from app.config import Settings, get_settings
from app.main import app
from app.middleware import entitlements as ent
from app.schedulers import storage_meter_scheduler as sched
from app.services import knowledge_sync_service as kss
from app.services import storage_meter as sm
from tests.services.storage_fakes import FakeClient

ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "33333333-3333-4333-8333-333333333333"
GIB = 1024**3
NOW = datetime(2026, 10, 13, 6, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    s = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    # Both ship on; tests start from off so each one says what it turns on.
    s.storage_meter_enabled = False
    s.storage_quota_enforcement_enabled = False
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _snapshot(client: FakeClient, total: int, *, captured: datetime | None = None) -> None:
    client.tables.setdefault("org_storage_usage_snapshots", []).append(
        {
            "org_id": ORG,
            "snapshot_date": (captured or datetime.now(UTC)).date().isoformat(),
            "captured_at": (captured or datetime.now(UTC)).isoformat(),
            "total_bytes": total,
            "categories": {"knowledge": {"bytes": total, "rows": 1}},
            "method": "proportional-relation-size-v1",
        }
    )


def _limit(monkeypatch, limit_bytes: int | None) -> None:
    monkeypatch.setattr(ent, "resolve_entitlements", lambda _s, _o: {"limits": {"storage_bytes": limit_bytes}})


# --------------------------------------------------------------------------- meter


def test_defaults_are_on():
    # Owner decision 2026-10-20: meter and quota ship on.
    fields = Settings.model_fields
    assert fields["storage_meter_enabled"].default is True
    assert fields["storage_quota_enforcement_enabled"].default is True


def test_scheduler_not_started_when_off(monkeypatch):
    monkeypatch.setattr(sched, "get_settings", lambda: _settings())
    assert sched.start_storage_meter_scheduler() is None


def test_aggregate_usage_sums_sources_per_category_and_ignores_unknown():
    rows = [
        {"org_id": ORG, "category": "knowledge", "source": "rag_chunks", "bytes": 100, "row_count": 4},
        {"org_id": ORG, "category": "knowledge", "source": "rag_embeddings", "bytes": 50, "row_count": 4},
        {"org_id": ORG, "category": "files", "source": "storage.objects:rag-uploads", "bytes": 7, "row_count": 1},
        {"org_id": ORG, "category": "mystery", "source": "x", "bytes": 999, "row_count": 1},
        {"org_id": OTHER, "category": "audit", "source": "audit_logs", "bytes": 3, "row_count": 3},
    ]
    out = sm.aggregate_usage(rows)
    assert out[ORG]["totalBytes"] == 157
    assert out[ORG]["categories"]["knowledge"] == {"bytes": 150, "rows": 8}
    assert out[ORG]["categories"]["memories"] == {"bytes": 0, "rows": 0}
    assert out[OTHER]["totalBytes"] == 3


def test_write_snapshots_upserts_one_row_per_org_per_day():
    client = FakeClient()
    client.rpc_handlers["compute_org_storage_usage"] = lambda p: [
        {"org_id": ORG, "category": "knowledge", "source": "rag_chunks", "bytes": 10, "row_count": 1},
        {"org_id": OTHER, "category": "audit", "source": "audit_logs", "bytes": 20, "row_count": 2},
    ]
    assert sm.write_storage_snapshots(client, now=NOW) == 2
    assert sm.write_storage_snapshots(client, now=NOW) == 2  # same day: replaced, not duplicated
    rows = client.tables["org_storage_usage_snapshots"]
    assert sorted((r["org_id"], r["total_bytes"]) for r in rows) == [(ORG, 10), (OTHER, 20)]
    assert client.rpc_calls("compute_org_storage_usage") == [{"p_org_id": None}] * 2


def test_usage_view_hidden_when_meter_off_without_touching_the_db():
    view = sm.storage_usage_view(None, _settings(), ORG, None)
    assert view["meterEnabled"] is False and view["snapshot"] is None and view["state"] == "unknown"


def test_usage_view_with_snapshot_reports_warn_at_80_percent():
    client = FakeClient()
    _snapshot(client, int(4.25 * GIB))
    view = sm.storage_usage_view(client, _settings(storage_meter_enabled=True), ORG, {"limits": {"storage_bytes": 5 * GIB}})
    assert view["state"] == "warn" and view["percentUsed"] == 85.0
    assert view["snapshot"]["categories"]["knowledge"]["bytes"] == int(4.25 * GIB)
    assert view["enforcementEnabled"] is False


def test_usage_view_without_snapshot_or_table():
    client = FakeClient()
    client.table_errors[("org_storage_usage_snapshots", "select")] = RuntimeError("relation does not exist")
    view = sm.storage_usage_view(client, _settings(storage_meter_enabled=True), ORG, {"limits": {"storage_bytes": GIB}})
    assert view["snapshot"] is None and view["state"] == "unknown"


@pytest.mark.parametrize(
    "used,limit,state",
    [(None, GIB, "unknown"), (5, None, "unlimited"), (79, 100, "ok"), (80, 100, "warn"), (100, 100, "over")],
)
def test_quota_state(used, limit, state):
    assert sm.quota_state(used, limit)[0] == state


# --------------------------------------------------------------------------- quota


def test_quota_off_never_blocks_or_reads(monkeypatch):
    client = FakeClient()
    _snapshot(client, 10 * GIB)
    _limit(monkeypatch, GIB)
    sm.ensure_storage_quota(client, _settings(), ORG, action="upload")
    assert client.calls == []


def test_quota_on_over_limit_refuses(monkeypatch):
    client = FakeClient()
    _snapshot(client, 2 * GIB)
    _limit(monkeypatch, GIB)
    with pytest.raises(sm.StorageQuotaExceededError) as err:
        sm.ensure_storage_quota(client, _settings(storage_quota_enforcement_enabled=True), ORG, action="upload")
    assert err.value.used_bytes == 2 * GIB and err.value.limit_bytes == GIB
    assert "Nothing has been deleted" in str(err.value)


def test_quota_on_warn_only_logs(monkeypatch, caplog):
    client = FakeClient()
    _snapshot(client, int(0.9 * GIB))
    _limit(monkeypatch, GIB)
    sm.ensure_storage_quota(client, _settings(storage_quota_enforcement_enabled=True), ORG, action="upload")
    assert any("storage_quota_warning" in r.getMessage() for r in caplog.records)


def test_quota_ignores_stale_snapshot_and_errors(monkeypatch):
    client = FakeClient()
    _snapshot(client, 9 * GIB, captured=datetime.now(UTC) - timedelta(days=5))
    _limit(monkeypatch, GIB)
    on = _settings(storage_quota_enforcement_enabled=True)
    assert sm.storage_quota_block_reason(client, on, ORG) is None
    broken = FakeClient()
    broken.table_errors[("org_storage_usage_snapshots", "select")] = RuntimeError("down")
    assert sm.storage_quota_block_reason(broken, on, ORG) is None


def test_scheduled_knowledge_sync_skips_over_quota_org_without_a_job(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(kss, "list_due_knowledge_connectors", lambda _c: [{"id": "c1", "org_id": ORG, "type": "notion"}])
    created = []
    monkeypatch.setattr(kss, "create_knowledge_sync_job", lambda *a, **k: created.append(k) or {"id": "j"})
    refusal = sm.StorageQuotaExceededError("over", used_bytes=2, limit_bytes=1)
    monkeypatch.setattr(sm, "storage_quota_block_reason", lambda *_a, **_k: refusal)
    out = kss.run_scheduled_knowledge_syncs(_settings(storage_quota_enforcement_enabled=True), client=client)
    assert out["outcomes"] == [{"connector_id": "c1", "status": "held", "reason": "storage_quota_exceeded"}]
    assert created == []


def test_manual_trigger_raises_before_any_job(monkeypatch):
    client = FakeClient()
    client.tables["connectors"] = [{"id": "c1", "org_id": ORG, "type": "notion", "deleted_at": None}]
    monkeypatch.setattr(kss, "create_knowledge_sync_job", lambda *a, **k: pytest.fail("job created"))
    monkeypatch.setattr(
        sm, "storage_quota_block_reason",
        lambda *_a, **_k: sm.StorageQuotaExceededError("over", used_bytes=2, limit_bytes=1),
    )
    with pytest.raises(sm.StorageQuotaExceededError):
        kss.trigger_connector_knowledge_sync(client, _settings(), ORG, "c1", actor_id="u1")


# --------------------------------------------------------------------------- API


@pytest.fixture
def api():
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(settings: Settings) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, ORG)


def test_usage_endpoint_meter_off(api):
    _auth(_settings())
    res = api.get("/api/settings/storage/usage")
    assert res.status_code == 200
    body = res.json()
    assert body["meterEnabled"] is False and body["snapshot"] is None


def test_usage_endpoint_returns_snapshot_and_limit(api, monkeypatch):
    client = FakeClient()
    _snapshot(client, GIB)
    import app.routers.storage_settings as routes

    monkeypatch.setattr(routes, "shared_service_client", lambda *_a, **_k: client)
    _limit(monkeypatch, 5 * GIB)
    _auth(_settings(storage_meter_enabled=True))
    body = api.get("/api/settings/storage/usage").json()
    assert body["limitBytes"] == 5 * GIB and body["state"] == "ok" and body["percentUsed"] == 20.0
    assert body["snapshot"]["totalBytes"] == GIB


def test_upload_refused_with_402_when_over_quota(api, monkeypatch):
    from app.routers import rag_admin

    def refuse(*_a, **_k):
        raise sm.StorageQuotaExceededError("Your workspace has used its storage allowance", used_bytes=2, limit_bytes=1)

    monkeypatch.setattr(rag_admin, "ensure_storage_quota", refuse)
    monkeypatch.setattr(rag_admin, "shared_service_client", lambda *_a, **_k: FakeClient())
    _auth(_settings(storage_quota_enforcement_enabled=True))
    res = api.post(
        "/api/rag/ingest",
        json={"source_id": "22222222-2222-4222-8222-222222222222", "text": "hello"},
    )
    assert res.status_code == 402
    body = res.json()
    assert body["code"] == "STORAGE_QUOTA_EXCEEDED"
    assert body["details"] == {"usedBytes": 2, "limitBytes": 1}


# --------------------------------------------------------------------------- plan limits


def _entitlements(monkeypatch, *, code: str, features: dict | None = None, addons: list | None = None) -> dict:
    monkeypatch.setattr(ent, "get_org_billing", lambda _c, _o: {"plan_code": code, "billing_status": "active"})
    monkeypatch.setattr(ent, "get_plan_for_org", lambda _c, _o, **_k: {"code": code, "features": features or {}})
    monkeypatch.setattr(
        ent, "_select_latest_subscription", lambda _c, _o: {"meson_addons": addons or [], "status": "active"}
    )
    monkeypatch.setattr(ent, "_usage_totals", lambda _c, _o: {})
    return ent._compute_entitlements(SimpleNamespace(), ORG)


def test_plan_storage_limits_and_byo_entitlement(monkeypatch):
    assert ent.TIER_LIMITS["free"]["storage_bytes"] == GIB
    node = _entitlements(monkeypatch, code="node")
    assert node["limits"]["storage_bytes"] == 5 * GIB
    assert node["features"]["byo_storage"] is False
    command = _entitlements(monkeypatch, code="command")
    assert command["limits"]["storage_bytes"] == 100 * GIB
    assert command["features"]["byo_storage"] is True
    custom = _entitlements(monkeypatch, code="control", features={"storage_gb": 50})
    assert custom["limits"]["storage_bytes"] == 50 * GIB
    unlimited = _entitlements(monkeypatch, code="control", features={"storage_gb": -1})
    assert unlimited["limits"]["storage_bytes"] is None
    addon = _entitlements(monkeypatch, code="control", addons=["byo_storage"])
    assert addon["features"]["byo_storage"] is True
