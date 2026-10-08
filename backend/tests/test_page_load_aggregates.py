"""SQL-aggregated page-load endpoints: RPC path, paged fallback, and parity.

Covers /api/metrics/overview counts (``metrics_overview_counts``) and marketplace
categories (``marketplace_category_counts``). The fake client below behaves like
PostgREST: filters, ``order``, ``range`` and a hard ``max_rows`` cap of 1000, so the
fallback must page to see every row.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from postgrest.exceptions import APIError

from app.core import sql_aggregates
from app.core.sql_aggregates import fetch_all_rows, is_missing_function_error
from app.marketplace.support import list_marketplace_categories
from app.routers.metrics import _overview_counts
from tests.support.build_insights import authenticate, clear_overrides
from tests.support.build_insights import client as http_client

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"
START = datetime(2026, 10, 1, tzinfo=UTC)
END = datetime(2026, 10, 8, tzinfo=UTC)
MAX_ROWS = 1000


@pytest.fixture(autouse=True)
def _reset():
    sql_aggregates.reset_fallback_log_state()
    yield
    sql_aggregates.reset_fallback_log_state()
    clear_overrides()


# ---------------------------------------------------------------------------
# Fake PostgREST
# ---------------------------------------------------------------------------


class FakeQuery:
    def __init__(self, store: FakeClient, table: str) -> None:
        self.store = store
        self.table = table
        self.filters: list[Callable[[dict[str, Any]], bool]] = []
        self.order_col: str | None = None
        self.bounds: tuple[int, int] | None = None

    def select(self, *_cols: str, **_kw: Any) -> FakeQuery:
        return self

    def eq(self, col: str, val: Any) -> FakeQuery:
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def gte(self, col: str, val: str) -> FakeQuery:
        self.filters.append(lambda r: r[col] >= datetime.fromisoformat(val))
        return self

    def lt(self, col: str, val: str) -> FakeQuery:
        self.filters.append(lambda r: r[col] < datetime.fromisoformat(val))
        return self

    def or_(self, expr: str) -> FakeQuery:
        match = re.fullmatch(r"visibility\.eq\.public,and\(visibility\.eq\.internal,org_id\.eq\.([^)]+)\)", expr)
        assert match, expr
        org = match.group(1)
        self.filters.append(
            lambda r: r.get("visibility") == "public"
            or (r.get("visibility") == "internal" and r.get("org_id") == org)
        )
        return self

    def order(self, col: str, **_kw: Any) -> FakeQuery:
        self.order_col = col
        return self

    def range(self, start: int, end: int) -> FakeQuery:
        self.bounds = (start, end)
        return self

    def execute(self) -> SimpleNamespace:
        self.store.selects.append((self.table, self.bounds))
        rows = [r for r in self.store.tables[self.table] if all(f(r) for f in self.filters)]
        if self.order_col:
            rows.sort(key=lambda r: r[self.order_col])
        if self.bounds:
            rows = rows[self.bounds[0] : self.bounds[1] + 1]
        return SimpleNamespace(data=[dict(r) for r in rows[:MAX_ROWS]])


class FakeClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]], rpc: Callable[[str, dict], Any] | None) -> None:
        self.tables = tables
        self._rpc = rpc
        self.rpc_calls: list[tuple[str, dict]] = []
        self.selects: list[tuple[str, tuple[int, int] | None]] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, name: str, params: dict) -> SimpleNamespace:
        self.rpc_calls.append((name, params))

        def _execute() -> SimpleNamespace:
            if self._rpc is None:
                raise APIError(
                    {
                        "code": "PGRST202",
                        "message": f"Could not find the function public.{name} in the schema cache",
                        "hint": None,
                        "details": None,
                    }
                )
            return SimpleNamespace(data=self._rpc(name, params))

        return SimpleNamespace(execute=_execute)


def _sql_semantics_rpc(tables: dict[str, list[dict[str, Any]]]) -> Callable[[str, dict], Any]:
    """Independent re-statement of the SQL in 20261008020000_page_load_aggregates.sql."""

    def _rpc(name: str, params: dict) -> Any:
        if name == "metrics_overview_counts":
            org = params["p_org_id"]
            start = datetime.fromisoformat(params["p_start_at"])
            end = datetime.fromisoformat(params["p_end_at"])
            wfs = [w for w in tables["workflow_defs"] if w["org_id"] == org]
            runs = [r for r in tables["workflow_runs"] if r["org_id"] == org and start <= r["created_at"] < end]
            conns = [c for c in tables["connectors"] if c["org_id"] == org]
            durations = [r["duration_ms"] for r in runs if r["duration_ms"] is not None]
            return {
                "total_workflows": len(wfs),
                "active_workflows": sum(1 for w in wfs if w["status"] == "active"),
                "total_runs": len(runs),
                "completed_runs": sum(1 for r in runs if r["status"] == "completed"),
                "failed_runs": sum(1 for r in runs if r["status"] == "failed"),
                "duration_count": len(durations),
                "duration_sum_ms": sum(durations),
                "total_connectors": len(conns),
                "active_connectors": sum(1 for c in conns if c["status"] == "active"),
            }
        if name == "marketplace_category_counts":
            org = params["p_org_id"]
            visible = [
                a
                for a in tables["marketplace_assets"]
                if a["status"] == "published"
                and (a["visibility"] == "public" or (a["visibility"] == "internal" and a["org_id"] == org))
            ]
            out: dict[str, Any] = {"categories": {}, "departments": {}, "asset_types": {}}
            for a in visible:
                for group, col, default in (
                    ("categories", "category", "uncategorized"),
                    ("departments", "department", "general"),
                    ("asset_types", "asset_type", "unknown"),
                ):
                    key = a[col] or default
                    out[group][key] = out[group].get(key, 0) + 1
            out["total_assets"] = len(visible)
            return out
        raise AssertionError(name)

    return _rpc


def _dataset() -> dict[str, list[dict[str, Any]]]:
    """Several tables larger than PostgREST's 1000-row cap."""
    in_window = datetime(2026, 10, 5, 12, tzinfo=UTC)
    out_window = datetime(2026, 9, 1, tzinfo=UTC)
    runs = [
        {
            "id": f"run-{i:05d}",
            "org_id": ORG_A,
            "status": ("running", "completed", "failed", "cancelled")[i % 4],
            "created_at": in_window if i % 3 else out_window,
            "duration_ms": None if i % 7 == 0 else i,
        }
        for i in range(2600)
    ]
    runs += [
        {"id": "run-start", "org_id": ORG_A, "status": "completed", "created_at": START, "duration_ms": 5},
        {"id": "run-end", "org_id": ORG_A, "status": "failed", "created_at": END, "duration_ms": 5},
        {"id": "run-org-b", "org_id": ORG_B, "status": "completed", "created_at": in_window, "duration_ms": 9},
    ]
    assets = [
        {
            "id": f"asset-{i:05d}",
            "org_id": None,
            "asset_type": ("workflow", "ai_agent", "knowledge_pack")[i % 3],
            "category": None if i % 10 == 0 else ("" if i % 10 == 1 else f"cat_{i % 4}"),
            "department": None if i % 9 == 0 else ("Sales", "Marketing", "Ops")[i % 3],
            "visibility": "public",
            "status": "published",
        }
        for i in range(2300)
    ]
    assets += [
        {"id": f"int-a-{i}", "org_id": ORG_A, "asset_type": "workflow", "category": "internal_a",
         "department": "Sales", "visibility": "internal", "status": "published"}
        for i in range(40)
    ]
    assets += [
        {"id": f"int-b-{i}", "org_id": ORG_B, "asset_type": "workflow", "category": "internal_b",
         "department": "Sales", "visibility": "internal", "status": "published"}
        for i in range(25)
    ]
    assets += [
        {"id": "priv-a", "org_id": ORG_A, "asset_type": "workflow", "category": "private_a",
         "department": "Sales", "visibility": "private", "status": "published"},
        {"id": "draft-pub", "org_id": None, "asset_type": "workflow", "category": "draft",
         "department": "Sales", "visibility": "public", "status": "draft"},
    ]
    return {
        "workflow_defs": [
            {"id": f"wf-{i:05d}", "org_id": ORG_A if i < 1500 else ORG_B, "status": "active" if i % 5 == 0 else "draft"}
            for i in range(1510)
        ],
        "workflow_runs": runs,
        "connectors": [
            {"id": f"c-{i:05d}", "org_id": ORG_A, "status": "active" if i % 3 == 0 else "error"}
            for i in range(1200)
        ],
        "marketplace_assets": assets,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_is_missing_function_error_codes():
    assert is_missing_function_error(APIError({"code": "PGRST202", "message": "x", "hint": None, "details": None}))
    assert is_missing_function_error(APIError({"code": "42883", "message": "x", "hint": None, "details": None}))
    assert is_missing_function_error(Exception("function public.metrics_overview_counts(uuid) does not exist"))
    assert not is_missing_function_error(APIError({"code": "57014", "message": "statement timeout", "hint": None, "details": None}))
    assert not is_missing_function_error(RuntimeError("connection reset"))


def test_fetch_all_rows_pages_past_max_rows():
    store = FakeClient({"t": [{"id": f"{i:05d}"} for i in range(2500)]}, rpc=None)
    rows = fetch_all_rows(lambda: store.table("t").select("id").order("id"))
    assert [r["id"] for r in rows] == [f"{i:05d}" for i in range(2500)]
    assert store.selects == [("t", (0, 999)), ("t", (1000, 1999)), ("t", (2000, 2999))]


def test_fetch_all_rows_exact_multiple_of_page_size():
    store = FakeClient({"t": [{"id": f"{i:05d}"} for i in range(2000)]}, rpc=None)
    rows = fetch_all_rows(lambda: store.table("t").select("id").order("id"))
    assert len(rows) == 2000
    assert len(store.selects) == 3  # last page is empty


# ---------------------------------------------------------------------------
# metrics_overview_counts
# ---------------------------------------------------------------------------


def test_overview_counts_rpc_path_uses_no_table_reads():
    tables = _dataset()
    fake = FakeClient(tables, rpc=_sql_semantics_rpc(tables))
    counts = _overview_counts(fake, ORG_A, START, END)
    assert fake.rpc_calls == [
        ("metrics_overview_counts", {"p_org_id": ORG_A, "p_start_at": START.isoformat(), "p_end_at": END.isoformat()})
    ]
    assert fake.selects == []
    assert counts["total_workflows"] == 1500
    assert counts["total_connectors"] == 1200


def test_overview_counts_fallback_pages_and_is_uncapped(caplog):
    tables = _dataset()
    fake = FakeClient(tables, rpc=None)
    with caplog.at_level(logging.WARNING, logger="app.core.sql_aggregates"):
        counts = _overview_counts(fake, ORG_A, START, END)
        _overview_counts(fake, ORG_A, START, END)

    in_window_runs = [r for r in tables["workflow_runs"] if r["org_id"] == ORG_A and START <= r["created_at"] < END]
    assert len(in_window_runs) > MAX_ROWS
    assert counts["total_workflows"] == 1500
    assert counts["active_workflows"] == 300
    assert counts["total_connectors"] == 1200
    assert counts["active_connectors"] == 400
    assert counts["total_runs"] == len(in_window_runs)
    assert counts["completed_runs"] == sum(1 for r in in_window_runs if r["status"] == "completed")
    # every table read was paged with .range()
    assert fake.selects and all(bounds is not None for _, bounds in fake.selects)
    fallback_logs = [r for r in caplog.records if "sql_aggregate_fallback" in r.getMessage()]
    assert len(fallback_logs) == 1


def test_overview_counts_rpc_and_fallback_match():
    tables = _dataset()
    via_rpc = _overview_counts(FakeClient(tables, rpc=_sql_semantics_rpc(tables)), ORG_A, START, END)
    via_fallback = _overview_counts(FakeClient(tables, rpc=None), ORG_A, START, END)
    assert set(via_rpc) == set(via_fallback)
    for key in via_rpc:
        assert float(via_rpc[key]) == float(via_fallback[key]), key


def test_overview_counts_other_rpc_errors_propagate():
    def _boom(_name: str, _params: dict) -> Any:
        raise APIError({"code": "57014", "message": "canceling statement due to statement timeout", "hint": None, "details": None})

    fake = FakeClient(_dataset(), rpc=_boom)
    with pytest.raises(APIError):
        _overview_counts(fake, ORG_A, START, END)
    assert fake.selects == []


def test_overview_counts_malformed_payload_falls_back():
    tables = _dataset()
    fake = FakeClient(tables, rpc=lambda _n, _p: {"total_runs": "lots"})
    counts = _overview_counts(fake, ORG_A, START, END)
    assert counts["total_workflows"] == 1500


@pytest.mark.parametrize("use_rpc", [True, False])
def test_overview_endpoint_response_identical_for_both_paths(use_rpc):
    tables = _dataset()
    fake = FakeClient(tables, rpc=_sql_semantics_rpc(tables) if use_rpc else None)
    service = {"range": "7d", "ingestion": {"chunks_embedded_total": 0}, "rag": {"retrieval_requests_total": 0}}
    with (
        patch("app.routers.metrics.create_client", return_value=fake),
        patch("app.routers.metrics.parse_range", return_value=("7d", START, END)),
        patch("app.routers.metrics.overview_metrics", return_value=dict(service)),
        patch("app.routers.metrics.connector_health_latency", return_value={"avg_latency_ms": 0.0, "p95_latency_ms": 0.0}),
        patch("app.routers.metrics.dashboard_run_stats", return_value={"changes": {}, "trends": {}}),
    ):
        authenticate(org_id=ORG_A)
        response = http_client.get("/api/metrics/overview?range=7d")
    assert response.status_code == 200
    body = response.json()

    in_window = [r for r in tables["workflow_runs"] if r["org_id"] == ORG_A and START <= r["created_at"] < END]
    completed = sum(1 for r in in_window if r["status"] == "completed")
    failed = sum(1 for r in in_window if r["status"] == "failed")
    durations = [float(r["duration_ms"]) for r in in_window if r["duration_ms"] is not None]
    assert body["totalWorkflows"] == 1500
    assert body["activeWorkflows"] == 300
    assert body["totalRuns"] == len(in_window)
    assert body["successRate"] == round(completed / (completed + failed) * 100, 2)
    assert body["avgLatency"] == round(sum(durations) / len(durations), 2)
    assert body["activeConnectors"] == 400
    assert body["totalConnectors"] == 1200
    assert isinstance(body["totalWorkflows"], int)


# ---------------------------------------------------------------------------
# marketplace_category_counts
# ---------------------------------------------------------------------------


def _expected_categories(tables: dict[str, list[dict[str, Any]]], org: str) -> dict[str, Any]:
    counts = _sql_semantics_rpc(tables)("marketplace_category_counts", {"p_org_id": org})

    def _sorted(values: dict[str, int]) -> list[dict[str, Any]]:
        return [{"key": k, "count": v} for k, v in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {
        "categories": _sorted(counts["categories"]),
        "departments": _sorted(counts["departments"]),
        "assetTypes": _sorted(counts["asset_types"]),
        "totalAssets": counts["total_assets"],
    }


def test_categories_rpc_path():
    tables = _dataset()
    fake = FakeClient(tables, rpc=_sql_semantics_rpc(tables))
    result = list_marketplace_categories(fake, ORG_A)
    assert fake.rpc_calls == [("marketplace_category_counts", {"p_org_id": ORG_A})]
    assert fake.selects == []
    assert result == _expected_categories(tables, ORG_A)
    assert result["totalAssets"] == 2340
    assert list(result) == ["categories", "departments", "assetTypes", "totalAssets"]


def test_categories_fallback_pages_past_1000(caplog):
    tables = _dataset()
    fake = FakeClient(tables, rpc=None)
    with caplog.at_level(logging.WARNING, logger="app.core.sql_aggregates"):
        result = list_marketplace_categories(fake, ORG_A)
        list_marketplace_categories(fake, ORG_B)
    assert result["totalAssets"] == 2340  # 2300 public + 40 internal to org A
    assert sum(item["count"] for item in result["categories"]) == 2340
    assert {"key": "uncategorized", "count": 460} in result["categories"]
    assert all(item["key"] not in {"internal_b", "private_a", "draft"} for item in result["categories"])
    assert fake.selects[:3] == [
        ("marketplace_assets", (0, 999)),
        ("marketplace_assets", (1000, 1999)),
        ("marketplace_assets", (2000, 2999)),
    ]
    assert len([r for r in caplog.records if "sql_aggregate_fallback" in r.getMessage()]) == 1


@pytest.mark.parametrize("org", [ORG_A, ORG_B, "33333333-3333-3333-3333-333333333333"])
def test_categories_rpc_and_fallback_match(org):
    tables = _dataset()
    via_rpc = list_marketplace_categories(FakeClient(tables, rpc=_sql_semantics_rpc(tables)), org)
    via_fallback = list_marketplace_categories(FakeClient(tables, rpc=None), org)
    assert via_rpc == via_fallback == _expected_categories(tables, org)


def test_categories_rpc_list_wrapped_payload_accepted():
    tables = _dataset()
    rpc = _sql_semantics_rpc(tables)
    fake = FakeClient(tables, rpc=lambda n, p: [rpc(n, p)])
    assert list_marketplace_categories(fake, ORG_A) == _expected_categories(tables, ORG_A)
    assert fake.selects == []
