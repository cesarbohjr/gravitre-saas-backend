from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.services.department_signal_scoring_service import (
    DepartmentSignalScoringService,
)


class _Table:
    def __init__(self, name: str, store: dict[str, list[dict[str, Any]]]) -> None:
        self.name = name
        self.store = store
        self._filters: list[tuple[str, Any, str]] = []
        self._limit: int | None = None
        self._order_key: str | None = None
        self._order_desc = False

    def select(self, *_cols: str, **_kwargs: Any) -> "_Table":
        return self

    def eq(self, key: str, value: Any) -> "_Table":
        self._filters.append((key, value, "eq"))
        return self

    def neq(self, key: str, value: Any) -> "_Table":
        self._filters.append((key, value, "neq"))
        return self

    def order(self, key: str, desc: bool = False) -> "_Table":
        self._order_key = key
        self._order_desc = desc
        return self

    def limit(self, value: int) -> "_Table":
        self._limit = value
        return self

    def execute(self) -> MagicMock:
        rows = [dict(row) for row in self.store.get(self.name, [])]
        for key, value, op in self._filters:
            if op == "eq":
                rows = [row for row in rows if row.get(key) == value]
            else:
                rows = [row for row in rows if row.get(key) != value]
        if self._order_key:
            rows.sort(key=lambda row: str(row.get(self._order_key) or ""), reverse=self._order_desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        out = MagicMock()
        out.data = rows
        return out


class _Client:
    def __init__(self, store: dict[str, list[dict[str, Any]]]) -> None:
        self.store = store

    def table(self, name: str) -> _Table:
        return _Table(name, self.store)


def _mock_engine(monkeypatch, *, connected: set[str], registered: set[str]) -> DepartmentSignalScoringService:
    engine = DepartmentSignalScoringService(settings=MagicMock())
    monkeypatch.setattr(engine, "_connected_integrations", lambda _client, _org_id: connected)
    monkeypatch.setattr(
        DepartmentSignalScoringService,
        "_registered_actions",
        staticmethod(lambda: registered),
    )
    return engine


def test_source_audit_classifies_live_kf_and_missing(monkeypatch) -> None:
    engine = _mock_engine(
        monkeypatch,
        connected={
            "apollo",
            "clay",
            "hubspot",
            "linkedin",
            "google_analytics",
            "google_ads",
            "google_search_console",
            "stripe",
            "quickbooks",
            "greenhouse",
            "nvd",
            "cisa_kev",
        },
        registered={
            "apollo.people.search",
            "clay.companies.enrich",
            "hubspot.contacts.list",
            "google_analytics.reports.run",
            "google_ads.reports.performance",
            "google_search_console.searchanalytics.query",
            "stripe.invoices.list",
            "quickbooks.payments.list",
            "greenhouse.jobs.list",
            "nvd.cve.get",
            "cisa_kev.feed.get",
        },
    )
    payload = engine.audit_sources("org-1", client=_Client({}), department=None)
    sales = next(row for row in payload["departments"] if row["department"] == "sales")
    census = next(row for row in sales["sources"] if row["sourceId"] == "sales.census_kf")
    assert census["status"] == "knowledge_fabric_only"
    msp = next(row for row in payload["departments"] if row["department"] == "msp")
    client_env = next(row for row in msp["sources"] if row["sourceId"] == "msp.client_environment")
    assert client_env["status"] == "missing"


def test_sales_scoring_is_weighted_and_explainable(monkeypatch) -> None:
    engine = _mock_engine(
        monkeypatch,
        connected={"apollo", "clay", "hubspot", "linkedin"},
        registered={"apollo.people.search", "clay.companies.enrich", "hubspot.contacts.list", "linkedin.prospect.enrich"},
    )
    store = {
        "work_objects": [
            {
                "id": "wo-1",
                "org_id": "org-1",
                "department": "sales",
                "object_type": "opportunity",
                "status": "in_progress",
                "title": "Acme expansion",
                "last_activity_at": "2026-09-04T00:00:00Z",
            },
            {
                "id": "wo-2",
                "org_id": "org-1",
                "department": "sales",
                "object_type": "opportunity",
                "status": "identified",
                "title": "Globex pilot",
                "last_activity_at": "2026-09-03T00:00:00Z",
            },
        ],
        "work_object_events": [
            {"org_id": "org-1", "work_object_id": "wo-1", "system_name": "hubspot", "created_at": "2026-09-04T00:00:00Z"},
            {"org_id": "org-1", "work_object_id": "wo-1", "system_name": "hubspot", "created_at": "2026-09-04T00:01:00Z"},
            {"org_id": "org-1", "work_object_id": "wo-1", "system_name": "apollo", "created_at": "2026-09-04T00:02:00Z"},
            {"org_id": "org-1", "work_object_id": "wo-2", "system_name": "apollo", "created_at": "2026-09-03T00:02:00Z"},
        ],
        "external_signals": [
            {"org_id": "org-1", "vendor": "clay", "signal_type": "enrichment", "detected_at": "2026-09-04T00:00:00Z"},
            {"org_id": "org-1", "vendor": "census", "signal_type": "business_formation", "detected_at": "2026-09-04T00:00:00Z"},
        ],
    }
    scored = engine.score_department("org-1", client=_Client(store), department="sales", limit=2)
    assert len(scored["priorities"]) == 2
    first = scored["priorities"][0]
    second = scored["priorities"][1]
    assert first["workObjectId"] == "wo-1"
    assert float(first["priorityScore"]) >= float(second["priorityScore"])
    assert first["signalContributions"]
    assert first["explanations"]

