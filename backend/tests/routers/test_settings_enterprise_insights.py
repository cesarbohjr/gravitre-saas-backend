"""Settings > Enterprise read models (/api/enterprise/insights/*): real-row aggregation only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers import settings_enterprise as mod

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
ADMIN = ({"user_id": "admin-1"}, "org-1")


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


class _Query:
    def __init__(self, db: "_Db", table: str):
        self.db = db
        self.table = table
        self.filters: list[tuple[str, str, object]] = []
        self.count_mode = None
        self._range: tuple[int, int] | None = None

    def select(self, *_a, count=None):
        self.count_mode = count
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, vals))
        return self

    def is_(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def update(self, payload):
        self.db.updates.append((self.table, payload))
        if self.table == "organizations":
            self.db.tables["organizations"][0].update(payload)
        return self

    def _rows(self):
        if self.table in self.db.missing:
            raise RuntimeError("relation does not exist")
        rows = list(self.db.tables.get(self.table, []))
        for op, col, val in self.filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col, val if col == "org_id" else None) == val]
            elif op == "gte":
                rows = [r for r in rows if str(r.get(col) or "") >= str(val)]
            elif op == "in":
                rows = [r for r in rows if r.get(col) in val]
        if self._range:
            rows = rows[self._range[0] : self._range[1] + 1]
        return rows

    def execute(self):
        rows = self._rows()
        return SimpleNamespace(data=rows, count=len(rows) if self.count_mode else None)


class _Db:
    def __init__(self, tables: dict[str, list[dict]], missing: set[str] | None = None):
        self.tables = tables
        self.missing = missing or set()
        self.updates: list[tuple[str, dict]] = []

    def table(self, name):
        return _Query(self, name)


def _directory_tables() -> dict[str, list[dict]]:
    return {
        "agents": [
            {"id": "a1", "name": "Lead Router", "department": "Sales", "created_at": _iso(3)},
            {"id": "a2", "name": "Health Monitor", "department": "Operations", "created_at": _iso(200)},
            {"id": "a3", "name": "Idle Agent", "department": None, "created_at": _iso(200)},
        ],
        "departments": [
            {"id": "d1", "name": "Sales"},
            {"id": "d2", "name": "Customer Success"},
            {"id": "d3", "name": "People Ops"},
        ],
        "department_resource_assignments": [
            {"department_id": "d2", "resource_id": "a2", "resource_type": "agent"},
        ],
    }


def _job(agent: str | None, days_ago: float) -> dict:
    payload = {"agent_id": agent} if agent else {}
    return {"id": f"j-{agent}-{days_ago}", "status": "completed", "payload": payload, "created_at": _iso(days_ago)}


# ---------------------------------------------------------------- knowledge sync


def test_knowledge_sync_overview_aggregates_days_status_and_kill_switch():
    connectors = [
        {"id": "c1", "name": "Notion", "type": "notion", "status": "healthy",
         "config": {"notion_sync_targets": ["p1"]}, "sync_frequency": "1h", "last_sync_at": _iso(0.1)},
        {"id": "c2", "name": "Zendesk", "type": "zendesk", "status": "active", "config": {}, "sync_frequency": None},
        {"id": "c3", "name": "Confluence", "type": "confluence", "status": "paused", "config": {}},
        {"id": "c4", "name": "HubSpot", "type": "hubspot", "status": "active",
         "config": {"hubspot_knowledge_sync_enabled": False}},
    ]
    jobs = [
        {"connector_id": "c1", "status": "completed", "created_at": _iso(0.2), "completed_at": _iso(0.2), "pages_synced": 7},
        {"connector_id": "c2", "status": "failed", "created_at": _iso(1), "error_message": "401 expired"},
        {"connector_id": "c1", "status": "completed", "created_at": _iso(3), "completed_at": _iso(3), "pages_synced": 5},
        {"connector_id": "c1", "status": "completed", "created_at": _iso(30), "completed_at": _iso(30), "pages_synced": 99},
    ]
    out = mod.build_knowledge_sync_overview(
        connectors=connectors, jobs=jobs, documents_indexed=42, ingestion_off=True,
        hold_reason_for=lambda _v: None, now=NOW,
    )
    assert out["ingestionDisabled"] is True
    assert len(out["days"]) == 14
    assert out["days"][-1] == {"date": NOW.date().isoformat(), "documents": 7}
    assert out["totalDocuments"] == 12  # the 30-day-old job is outside the window
    assert out["failedJobs"] == 1
    assert out["documentsIndexed"] == 42
    by_name = {s["name"]: s for s in out["sources"]}
    assert by_name["Notion"]["status"] == "healthy"
    assert by_name["Notion"]["schedule"] == "Every hour"
    assert by_name["Notion"]["docs14d"] == 12
    assert by_name["Zendesk"]["status"] == "failed"
    assert by_name["Zendesk"]["lastError"] == "401 expired"
    assert by_name["Zendesk"]["schedule"] == "Daily"
    assert by_name["Confluence"]["status"] == "paused"
    assert by_name["HubSpot"]["status"] == "not_configured"
    assert out["sourcesSyncing"] == 2


def test_knowledge_sync_empty_org_has_zero_days_not_samples():
    out = mod.build_knowledge_sync_overview(
        connectors=[], jobs=[], documents_indexed=None, ingestion_off=False,
        hold_reason_for=lambda _v: None, now=NOW,
    )
    assert out["sources"] == [] and out["totalDocuments"] == 0
    assert all(day["documents"] == 0 for day in out["days"])
    assert out["lastSyncAt"] is None and out["documentsIndexed"] is None


def test_knowledge_sync_route_reads_connectors_jobs_and_doc_count():
    db = _Db({
        "connectors": [{"id": "c1", "org_id": "org-1", "name": "Notion", "type": "notion", "status": "active",
                        "config": {"notion_sync_targets": ["x"]}}],
        "knowledge_sync_jobs": [{"org_id": "org-1", "connector_id": "c1", "status": "running",
                                 "created_at": datetime.now(timezone.utc).isoformat()}],
        "rag_documents": [{"id": "d1", "org_id": "org-1"}, {"id": "d2", "org_id": "org-1"}],
    })
    settings = SimpleNamespace(disable_ingestion=True)
    with patch.object(mod, "shared_service_client", return_value=db):
        out = mod.knowledge_sync_overview(ADMIN, settings)
    assert out["ingestionDisabled"] is True
    assert out["sources"][0]["status"] == "syncing"
    assert out["documentsIndexed"] == 2


# ---------------------------------------------------------------- residency


def test_residency_only_deployment_region_available():
    out = mod.build_residency(org_id="org-1", org_region="us", deployment_region="us")
    regions = {r["id"]: r for r in out["regions"]}
    assert regions["us"] == {"id": "us", "label": "United States", "current": True, "available": True}
    assert regions["eu"]["available"] is False and regions["eu"]["current"] is False
    assert out["storagePrefix"] == "us/org-1"
    assert out["migrationSupported"] is False


# ---------------------------------------------------------------- workforce


def test_workforce_counts_compare_previous_period_and_departments():
    directory, departments = mod.load_agent_directory(_Db(_directory_tables()), "org-1")
    assert directory["a2"]["department"] == "Customer Success"  # assignment wins over agents.department
    jobs = [_job("a1", 1), _job("a1", 2), _job("a2", 5), _job(None, 6), _job("a1", 10)]
    out = mod.build_workforce(jobs=jobs, directory=directory, department_names=departments, period_days=7, now=NOW)
    assert out["tasksCompleted"] == 4
    assert out["previousTasksCompleted"] == 1
    assert out["changePct"] == 300
    assert out["activeAgents"] == 2
    assert out["newAgents"] == 1
    assert out["departmentsTotal"] == 3
    assert out["departmentsUsing"] == 2
    assert out["departmentsIdle"] == ["People Ops"]
    assert out["byDepartment"][0] == {"name": "Sales", "tasks": 2}
    assert {"name": "No agent recorded", "tasks": 1} in out["byDepartment"]
    assert out["busiestAgents"][0]["name"] == "Lead Router"


def test_workforce_no_previous_period_has_no_change_pct():
    out = mod.build_workforce(jobs=[_job("a1", 1)], directory={}, department_names=[], period_days=30, now=NOW)
    assert out["changePct"] is None
    assert out["busiestAgents"][0]["name"] == "Unknown agent"


def test_workforce_route_reads_completed_jobs():
    tables = _directory_tables()
    tables["agent_jobs"] = [{**_job("a1", 0.5), "org_id": "org-1"}, {**_job("a1", 0.5), "status": "failed", "org_id": "org-1"}]
    for name in ("agents", "departments", "department_resource_assignments"):
        for row in tables[name]:
            row["org_id"] = "org-1"
    with patch.object(mod, "shared_service_client", return_value=_Db(tables)):
        out = mod.workforce(ADMIN, MagicMock(), days=30)
    assert out["tasksCompleted"] == 1


# ---------------------------------------------------------------- cost


def test_cost_attribution_by_agent_and_department():
    directory, _ = mod.load_agent_directory(_Db(_directory_tables()), "org-1")
    rows = [
        {"agent_id": "a1", "cost_usd": 1.5, "run_id": "r1"},
        {"agent_id": "a1", "cost_usd": 0.5, "run_id": "r1"},
        {"agent_id": "a2", "cost_usd": 1.0, "run_id": "r2"},
        {"agent_id": None, "cost_usd": 0.25, "run_id": None},
    ]
    out = mod.build_cost_attribution(rows=rows, directory=directory, source="model_calls", period_start=NOW, now=NOW)
    assert out["totalCostUsd"] == 3.25
    assert out["agentCount"] == 2
    assert out["byAgent"][0] == {"id": "a1", "name": "Lead Router", "department": "Sales", "costUsd": 2.0, "calls": 2, "runs": 1}
    depts = {d["name"]: d for d in out["byDepartment"]}
    assert depts["Customer Success"]["costUsd"] == 1.0
    assert depts["No department"]["agentCount"] == 0


def test_cost_route_empty_when_no_cost_rows():
    db = _Db({"organizations": [{"id": "org-1"}]}, missing={"usage_events"})
    with patch.object(mod, "shared_service_client", return_value=db):
        out = mod.cost_attribution(ADMIN, MagicMock())
    assert out["totalCostUsd"] == 0 and out["byAgent"] == [] and out["source"] is None


# ---------------------------------------------------------------- agent ROI


def test_agent_roi_needs_rate_and_minutes_no_defaults():
    directory, _ = mod.load_agent_directory(_Db(_directory_tables()), "org-1")
    jobs = [_job("a1", 1), _job("a1", 2), _job("a2", 3)]
    cost = [{"agent_id": "a1", "cost_usd": 0.5}, {"agent_id": "a2", "cost_usd": 1.0}]
    no_rate = mod.build_agent_roi(
        jobs=jobs, cost_rows=cost, directory=directory, rate=None, minutes={"a1": 30},
        period_days=30, period_start=NOW - timedelta(days=30), now=NOW,
    )
    assert no_rate["laborUsdPerHour"] is None
    assert no_rate["rows"] == []
    assert no_rate["totals"]["laborValueUsd"] is None

    out = mod.build_agent_roi(
        jobs=jobs, cost_rows=cost, directory=directory, rate=60.0, minutes={"a1": 30},
        period_days=30, period_start=NOW - timedelta(days=30), now=NOW,
    )
    assert [r["agentId"] for r in out["rows"]] == ["a1"]
    row = out["rows"][0]
    assert row["laborValueUsd"] == 60.0  # 2 tasks x 30 min x $60/h
    assert row["returnMultiple"] == 120.0
    assert out["hiddenWithoutEstimate"] == 1  # a2 has tasks but no minutes
    assert out["totals"] == {"agentCostUsd": 0.5, "laborValueUsd": 60.0, "netValueUsd": 59.5, "returnMultiple": 120.0}


def test_read_roi_inputs_ignores_bad_values():
    rate, minutes = mod.read_roi_inputs({"roi_labor_usd_per_hour": "abc", "roi_minutes_per_task_by_agent": {"a": 5, "b": -1, "c": "x"}})
    assert rate is None and minutes == {"a": 5.0}
    assert mod.read_roi_inputs({"labor_usd_per_hour": 70})[0] == 70.0


@pytest.fixture
def org_db():
    db = _Db({"organizations": [{"id": "org-1", "settings": {"other": 1}}]})
    with (
        patch.object(mod, "shared_service_client", return_value=db),
        patch("app.core.org_state_cache.invalidate_org_state"),
        patch.object(mod, "write_audit_event") as audit,
    ):
        yield db, audit


def test_update_agent_roi_inputs_persists_in_org_settings(org_db):
    db, audit = org_db
    body = mod.AgentRoiInputsUpdate(laborUsdPerHour=52.5, minutesPerTask={"a1": 12, "a2": None})
    out = mod.update_agent_roi_inputs(body, ADMIN, MagicMock())
    assert out == {"laborUsdPerHour": 52.5, "minutesPerTask": {"a1": 12.0}}
    saved = db.tables["organizations"][0]["settings"]
    assert saved["other"] == 1 and saved["roi_labor_usd_per_hour"] == 52.5
    assert audit.call_args.kwargs["action"] == "enterprise.agent_roi.inputs_updated"

    cleared = mod.update_agent_roi_inputs(mod.AgentRoiInputsUpdate(clearRate=True), ADMIN, MagicMock())
    assert cleared["laborUsdPerHour"] is None


def test_update_agent_roi_rejects_out_of_range_minutes(org_db):
    db, _ = org_db
    with pytest.raises(HTTPException) as exc:
        mod.update_agent_roi_inputs(mod.AgentRoiInputsUpdate(minutesPerTask={"a1": 5000}), ADMIN, MagicMock())
    assert exc.value.status_code == 400
    assert db.updates == []


def test_insights_routes_are_admin_only_and_mounted():
    from fastapi.testclient import TestClient

    from app.auth.dependencies import require_admin
    from app.main import app

    client = TestClient(app)
    for suffix in ("knowledge-sync", "residency", "workforce", "cost", "agent-roi"):
        # Mounted under the enterprise router: unauthenticated calls are refused, not 404.
        assert client.get(f"/api/enterprise/insights/{suffix}").status_code in {401, 403}
    for route in mod.router.routes:
        deps = [d.call for d in route.dependant.dependencies]
        assert require_admin in deps, route.path


def test_siem_test_event_uses_saved_endpoint_and_secret():
    from app.routers import enterprise as ent

    org = {"settings": {"enterprise": {"siem": {"endpoint": "https://siem.example.com/in", "secretEnc": "x"}}}}
    with (
        patch.object(ent, "shared_service_client", return_value=MagicMock()),
        patch.object(ent, "_org_settings", return_value=org["settings"]),
        patch.object(ent, "resolve_siem_secret", return_value="s3cret"),
        patch.object(ent, "dispatch_siem_event", return_value={"ok": True}) as dispatch,
    ):
        assert ent.test_siem_delivery(ent.SiemTestRequest(), ADMIN, MagicMock()) == {"ok": True}
    assert dispatch.call_args.kwargs["endpoint"] == "https://siem.example.com/in"
    assert dispatch.call_args.kwargs["secret"] == "s3cret"


def test_siem_test_event_without_saved_config_is_400():
    from app.routers import enterprise as ent

    with (
        patch.object(ent, "shared_service_client", return_value=MagicMock()),
        patch.object(ent, "_org_settings", return_value={}),
        patch.object(ent, "dispatch_siem_event") as dispatch,
    ):
        with pytest.raises(HTTPException) as exc:
            ent.test_siem_delivery(ent.SiemTestRequest(), ADMIN, MagicMock())
    assert exc.value.status_code == 400
    dispatch.assert_not_called()
