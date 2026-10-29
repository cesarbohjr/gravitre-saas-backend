"""Connector detail extras for the Connectors redesign: granted scopes and the audit trail."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers import connectors as connectors_router

CONNECTOR_ID = "11111111-1111-1111-1111-111111111111"
OTHER_ID = "22222222-2222-2222-2222-222222222222"


class _Table:
    def __init__(self, client: _Client, name: str) -> None:
        self.client = client
        self.name = name
        self._filters: list[tuple[str, Any]] = []
        self._limit: int | None = None
        self._desc = False

    def select(self, *_a: Any, **_k: Any) -> _Table:
        return self

    def eq(self, key: str, value: Any) -> _Table:
        self._filters.append((key, value))
        return self

    def is_(self, key: str, value: Any) -> _Table:
        if value == "null":
            self._filters.append((key, None))
        return self

    def order(self, _key: str, desc: bool = False) -> _Table:
        self._desc = desc
        return self

    def limit(self, value: int) -> _Table:
        self._limit = value
        return self

    def execute(self) -> MagicMock:
        rows = [dict(r) for r in self.client.store.get(self.name, [])]
        for key, value in self._filters:
            rows = [r for r in rows if r.get(key) == value]
        if self._desc:
            rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        total = len(rows)
        if self._limit is not None:
            rows = rows[: self._limit]
        out = MagicMock()
        out.data = rows
        out.count = total
        return out


class _Client:
    def __init__(self, store: dict[str, list[dict[str, Any]]]) -> None:
        self.store = store

    def table(self, name: str) -> _Table:
        return _Table(self, name)


def _store() -> dict[str, list[dict[str, Any]]]:
    return {
        "connectors": [
            {"id": CONNECTOR_ID, "org_id": "org-1", "environment": "production", "deleted_at": None},
        ],
        "audit_events": [
            {
                "id": f"e{i}",
                "org_id": "org-1",
                "resource_type": "connector",
                "resource_id": CONNECTOR_ID,
                "action": "connector.sync.manual" if i % 2 else "connector.config.updated",
                "actor_id": "user-1",
                "metadata": {"environment": "production"},
                "created_at": f"2026-10-2{i}T09:00:00Z",
            }
            for i in range(5)
        ]
        + [
            {
                "id": "other",
                "org_id": "org-1",
                "resource_type": "connector",
                "resource_id": OTHER_ID,
                "action": "connector.deleted",
                "created_at": "2026-10-26T09:00:00Z",
            },
            {
                "id": "other-org",
                "org_id": "org-2",
                "resource_type": "connector",
                "resource_id": CONNECTOR_ID,
                "action": "connector.deleted",
                "created_at": "2026-10-26T09:00:00Z",
            },
        ],
    }


def _call_activity(monkeypatch, client: _Client, connector_id: str, limit: int = 50) -> dict[str, Any]:
    monkeypatch.setattr(connectors_router, "create_client", lambda *_a, **_k: client)
    monkeypatch.setattr(connectors_router, "shared_service_client", lambda _s, factory: factory())
    from uuid import UUID

    return connectors_router.connector_activity_route(
        connector_id=UUID(connector_id),
        _user={"user_id": "user-1"},
        org_id="org-1",
        environment_name="production",
        settings=SimpleNamespace(),
        limit=limit,
    )


def test_activity_lists_only_this_connectors_events_newest_first(monkeypatch) -> None:
    payload = _call_activity(monkeypatch, _Client(_store()), CONNECTOR_ID, limit=3)
    assert payload["total"] == 5
    assert [e["id"] for e in payload["events"]] == ["e4", "e3", "e2"]
    assert payload["events"][0]["action"] == "connector.config.updated"
    assert payload["events"][0]["createdAt"] == "2026-10-24T09:00:00Z"


def test_activity_404s_for_a_connector_outside_the_org(monkeypatch) -> None:
    with pytest.raises(HTTPException) as exc:
        _call_activity(monkeypatch, _Client(_store()), OTHER_ID)
    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    ("tokens", "scopes", "expires"),
    [
        ({"scopes": ["crm.lists.write", "crm.objects.deals.read"], "expires_at": 1793001600},
         ["crm.lists.write", "crm.objects.deals.read"], "2026-10-26T08:00:00+00:00"),
        ({"scope": "read write read", "access_token": "secret"}, ["read", "write"], None),
        ({"access_token": "secret"}, [], None),
    ],
)
def test_oauth_credentials_summary_never_returns_tokens(monkeypatch, tokens, scopes, expires) -> None:
    monkeypatch.setattr(connectors_router, "get_decrypted_secret", lambda *_a, **_k: json.dumps(tokens))
    summary = connectors_router._oauth_credentials_summary(None, CONNECTOR_ID, SimpleNamespace(), org_id="org-1")
    assert summary == {"hasOAuthTokens": True, "grantedScopes": scopes, "tokenExpiresAt": expires}
    assert "secret" not in json.dumps(summary)


def test_oauth_credentials_summary_without_tokens(monkeypatch) -> None:
    monkeypatch.setattr(connectors_router, "get_decrypted_secret", lambda *_a, **_k: None)
    summary = connectors_router._oauth_credentials_summary(None, CONNECTOR_ID, SimpleNamespace(), org_id="org-1")
    assert summary == {"hasOAuthTokens": False, "grantedScopes": [], "tokenExpiresAt": None}
