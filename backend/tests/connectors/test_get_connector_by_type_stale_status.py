"""get_connector_by_type must still find a row when live auth outranks stale error status."""
from __future__ import annotations

from types import SimpleNamespace

from app.connectors.repository import get_connector_by_type


class _Result:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._eq: dict[str, object] = {}
        self._in_status: list[str] | None = None

    def select(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def eq(self, key: str, value: object) -> _Query:
        self._eq[key] = value
        return self

    def in_(self, key: str, values: list[str]) -> _Query:
        if key == "status":
            self._in_status = list(values)
        return self

    def is_(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def order(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def limit(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def execute(self) -> _Result:
        out: list[dict] = []
        for row in self._rows:
            if any(row.get(k) != v for k, v in self._eq.items()):
                continue
            if self._in_status is not None and row.get("status") not in self._in_status:
                continue
            out.append(row)
        return _Result(out[:1])


class _Client:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def table(self, _name: str) -> _Query:
        return _Query(self._rows)


def test_get_connector_by_type_falls_back_from_stale_error_status() -> None:
    row = {
        "id": "ga-1",
        "org_id": "org-1",
        "type": "google_analytics",
        "status": "error",
        "environment": "production",
        "config": {"property_id": "123"},
        "created_at": "t0",
        "updated_at": "t1",
    }
    found = get_connector_by_type(_Client([row]), "org-1", "google_analytics")
    assert found is not None
    assert found["id"] == "ga-1"
    assert found["status"] == "error"
    assert found["config"]["property_id"] == "123"


def test_get_connector_by_type_prefers_healthy_over_error() -> None:
    rows = [
        {
            "id": "ga-error",
            "org_id": "org-1",
            "type": "google_analytics",
            "status": "error",
            "environment": "production",
            "config": {},
        },
        {
            "id": "ga-ok",
            "org_id": "org-1",
            "type": "google_analytics",
            "status": "healthy",
            "environment": "production",
            "config": {"property_id": "999"},
        },
    ]
    found = get_connector_by_type(_Client(rows), "org-1", "google_analytics")
    assert found is not None
    assert found["id"] == "ga-ok"


def test_resolve_ga4_property_reads_linked_config_on_error_status(monkeypatch) -> None:
    from app.services import connector_resource_resolver as resolver

    row = {
        "id": "ga-1",
        "config": {"property_id": "555", "property_name": "Site"},
        "status": "error",
    }
    monkeypatch.setattr(resolver, "_connector_row", lambda *a, **k: row)
    resolution = resolver.resolve_ga4_property(
        client=SimpleNamespace(),
        org_id="org-1",
        settings=SimpleNamespace(),
    )
    assert resolution.status == "resolved"
    assert resolution.resource_id == "555"
