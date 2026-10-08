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


class _CountingClient(_Client):
    def __init__(self, store: dict[str, list[dict[str, Any]]]) -> None:
        super().__init__(store)
        self.calls: list[str] = []

    def table(self, name: str) -> _Table:
        self.calls.append(name)
        return super().table(name)

    def count(self, name: str) -> int:
        return sum(1 for n in self.calls if n == name)


def _multi_department_store() -> dict[str, list[dict[str, Any]]]:
    work_objects: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for dept, otype, systems in (
        ("sales", "opportunity", ("hubspot", "apollo")),
        ("marketing", "campaign", ("google_analytics", "google_ads")),
        ("finance", "invoice", ("stripe", "quickbooks")),
        ("hr", "requisition", ("greenhouse",)),
        # msp intentionally has no rows (exercises the object_type fallback query).
    ):
        for i in range(4):
            wid = f"{dept}-wo-{i}"
            work_objects.append(
                {
                    "id": wid,
                    "org_id": "org-1",
                    "department": dept,
                    "object_type": otype,
                    "status": "in_progress",
                    "title": f"{dept} item {i}",
                    "last_activity_at": f"2026-09-0{i + 1}T00:00:00Z",
                }
            )
            for j, system in enumerate(systems[: (i % len(systems)) + 1]):
                events.append(
                    {
                        "org_id": "org-1",
                        "work_object_id": wid,
                        "system_name": system,
                        "created_at": f"2026-09-0{i + 1}T00:0{j}:00Z",
                    }
                )
    events.append(
        {"org_id": "org-2", "work_object_id": "sales-wo-0", "system_name": "hubspot", "created_at": "2026-09-09T00:00:00Z"}
    )
    return {
        "work_objects": work_objects,
        "work_object_events": events,
        "external_signals": [
            {"org_id": "org-1", "vendor": "clay", "signal_type": "enrichment", "detected_at": "2026-09-04T00:00:00Z"},
            {"org_id": "org-1", "vendor": "stripe", "signal_type": "payment", "detected_at": "2026-09-03T00:00:00Z"},
            {"org_id": "org-1", "vendor": "nvd", "signal_type": "cve", "detected_at": "2026-09-02T00:00:00Z"},
        ],
    }


def _strip_timestamps(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("capturedAt", None)
    if "departments" in out:
        out["departments"] = [_strip_timestamps(row) for row in out["departments"]]
    return out


def test_score_all_departments_loads_org_inputs_once_and_matches_per_department(monkeypatch) -> None:
    connected = {"apollo", "clay", "hubspot", "google_analytics", "google_ads", "stripe", "quickbooks", "greenhouse", "nvd"}
    engine = _mock_engine(monkeypatch, connected=connected, registered=set())
    integration_calls: list[str] = []

    def _connected(_client: Any, org_id: str) -> set[str]:
        integration_calls.append(org_id)
        return set(connected)

    monkeypatch.setattr(engine, "_connected_integrations", _connected)

    # Legacy behaviour: each department scored independently (inputs re-read per department).
    legacy_client = _CountingClient(_multi_department_store())
    legacy = {
        "departments": [
            engine.score_department("org-1", client=legacy_client, department=dept, limit=3)
            for dept in ("sales", "marketing", "finance", "hr", "msp")
        ]
    }
    assert len(integration_calls) == 5
    assert legacy_client.count("work_object_events") == 4  # every department with work objects
    assert legacy_client.count("external_signals") == 4

    integration_calls.clear()
    client = _CountingClient(_multi_department_store())
    batched = engine.score_all_departments("org-1", client=client, limit_per_department=3)

    assert _strip_timestamps(batched) == _strip_timestamps(legacy)
    assert len(integration_calls) == 1
    assert client.count("work_object_events") == 1
    assert client.count("external_signals") == 1
    # Work objects stay per-department (bounded, LIMITed queries): unchanged.
    assert client.count("work_objects") == legacy_client.count("work_objects")
    assert len(client.calls) == len(legacy_client.calls) - 6
    sales = next(row for row in batched["departments"] if row["department"] == "sales")
    assert sales["priorities"]


def test_score_all_departments_skips_event_queries_when_no_work_objects(monkeypatch) -> None:
    engine = _mock_engine(monkeypatch, connected=set(), registered=set())
    client = _CountingClient({})
    payload = engine.score_all_departments("org-1", client=client)
    assert all(not row["priorities"] for row in payload["departments"])
    assert client.count("work_object_events") == 0
    assert client.count("external_signals") == 0

