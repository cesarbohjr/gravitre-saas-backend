"""GET /api/connectors reads connector_secrets once (batched), not once per connector."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.connectors import connector_availability_service
from app.connectors.crypto import encrypt_secret
from app.connectors.repository import get_decrypted_secrets_bulk
from app.routers import connectors as connectors_router

_KEY = "ab" * 32


class _Table:
    def __init__(self, client: _Client, name: str) -> None:
        self.client = client
        self.name = name
        self._filters: list[tuple[str, str, Any]] = []
        self._limit: int | None = None

    def select(self, *_a: Any, **_k: Any) -> _Table:
        return self

    def eq(self, key: str, value: Any) -> _Table:
        self._filters.append(("eq", key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> _Table:
        self._filters.append(("in", key, list(values)))
        return self

    def is_(self, key: str, value: Any) -> _Table:
        self._filters.append(("is", key, value))
        return self

    def order(self, *_a: Any, **_k: Any) -> _Table:
        return self

    def limit(self, value: int) -> _Table:
        self._limit = value
        return self

    def execute(self) -> MagicMock:
        self.client.executions.append(self.name)
        rows = [dict(r) for r in self.client.store.get(self.name, [])]
        for op, key, value in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(key) == value]
            elif op == "in":
                rows = [r for r in rows if r.get(key) in value]
            elif op == "is" and value == "null":
                rows = [r for r in rows if r.get(key) is None]
        if self._limit is not None:
            rows = rows[: self._limit]
        out = MagicMock()
        out.data = rows
        out.error = None
        return out


class _Client:
    def __init__(self, store: dict[str, list[dict[str, Any]]]) -> None:
        self.store = store
        self.executions: list[str] = []

    def table(self, name: str) -> _Table:
        return _Table(self, name)

    def count(self, name: str) -> int:
        return sum(1 for n in self.executions if n == name)


def _connector(cid: str, vendor: str | None) -> dict[str, Any]:
    return {
        "id": cid,
        "org_id": "org-1",
        "name": f"{vendor or 'stub'}-{cid}",
        "vendor": vendor,
        "type": vendor,
        "status": "active",
        "environment": "production",
        "config": {"auth_type": "api_key"},
        "deleted_at": None,
        "api_key_encrypted": None,
        "webhook_url": None,
    }


def _store() -> dict[str, list[dict[str, Any]]]:
    return {
        "connectors": [
            _connector("c1", "stripe"),
            _connector("c2", "clay"),  # no secret row
            _connector("c3", "semrush"),  # undecryptable secret
            _connector("c4", None),  # hidden: vendor-less stub
            _connector("c5", "ahrefs"),
        ],
        "connector_secrets": [
            {"connector_id": "c1", "key_name": "api_key", "encrypted_value": encrypt_secret("sk_live_1234", _KEY)},
            {"connector_id": "c1", "key_name": "oauth_tokens", "encrypted_value": encrypt_secret("{}", _KEY)},
            {"connector_id": "c3", "key_name": "api_key", "encrypted_value": "not-a-fernet-token"},
            {"connector_id": "c4", "key_name": "api_key", "encrypted_value": encrypt_secret("hidden9999", _KEY)},
            {"connector_id": "c5", "key_name": "api_key", "encrypted_value": encrypt_secret("ah_abcd5678", _KEY)},
        ],
    }


@pytest.fixture
def settings() -> SimpleNamespace:
    return SimpleNamespace(
        connector_secrets_encryption_key=_KEY,
        encryption_key="",
        supabase_url="http://fake",
        supabase_service_role_key="fake",
    )


@pytest.fixture(autouse=True)
def _stub_availability(monkeypatch) -> None:
    def _fake_eval(_client, _org_id, row, _settings, **_kwargs):
        return {
            "health_status": "healthy",
            "auth_status": None,
            "display_status": "connected",
            "configured": True,
            "authenticated": True,
            "token_valid": True,
            "scopes_valid": True,
            "execution_available": True,
            "blocking_reason": None,
            "recovery_action": None,
            "last_checked_at": "2026-10-01T00:00:00Z",
            "source_of_truth": "test",
        }

    monkeypatch.setattr(connector_availability_service, "evaluate_connector_availability", _fake_eval)


def _legacy_per_connector_output(client: _Client, settings: SimpleNamespace) -> list[dict[str, Any]]:
    """The pre-batching shape: one connector_secrets read inside each item."""
    rows = [r for r in client.store["connectors"] if connectors_router._visible_on_connectors_hub(r)]
    return [
        connectors_router._connector_response_item(
            row,
            environment_name="production",
            settings=settings,
            client=client,
            org_id="org-1",
        )
        for row in rows
    ]


def _call_route(client: _Client, settings: SimpleNamespace, monkeypatch) -> dict[str, Any]:
    monkeypatch.setattr(connectors_router, "create_client", lambda *_a, **_k: client)
    return connectors_router.list_connectors_route_alias(
        _user={"id": "u1"},
        org_id="org-1",
        environment_name="production",
        settings=settings,
        live=False,
    )


def test_list_connectors_reads_secrets_once_and_matches_legacy_output(monkeypatch, settings) -> None:
    legacy_client = _Client(_store())
    legacy = _legacy_per_connector_output(legacy_client, settings)
    assert legacy_client.count("connector_secrets") == 4  # one per visible connector

    client = _Client(_store())
    payload = _call_route(client, settings, monkeypatch)

    assert client.count("connector_secrets") == 1
    assert client.count("connectors") == 1
    assert payload["connectors"] == legacy
    by_id = {item["id"]: item for item in payload["connectors"]}
    assert set(by_id) == {"c1", "c2", "c3", "c5"}
    assert by_id["c1"]["config"]["apiKey"] == "••••••••1234"
    assert by_id["c2"]["config"]["apiKey"] is None  # no secret row
    assert by_id["c3"]["config"]["apiKey"] is None  # undecryptable
    assert by_id["c5"]["config"]["apiKey"] == "••••••••5678"


def test_list_connectors_falls_back_to_per_connector_reads_when_bulk_fails(monkeypatch, settings) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("bulk read failed")

    monkeypatch.setattr(connectors_router, "get_decrypted_secrets_bulk", _boom)
    legacy = _legacy_per_connector_output(_Client(_store()), settings)
    client = _Client(_store())
    payload = _call_route(client, settings, monkeypatch)
    assert payload["connectors"] == legacy
    assert client.count("connector_secrets") == 4


def test_get_decrypted_secrets_bulk_chunks_and_maps_every_id(settings) -> None:
    ids = [f"c{i}" for i in range(450)]
    store = {
        "connector_secrets": [
            {"connector_id": cid, "key_name": "api_key", "encrypted_value": encrypt_secret(f"v-{cid}", _KEY)}
            for cid in ids[::3]
        ]
    }
    client = _Client(store)
    out = get_decrypted_secrets_bulk(client, ids + ["c0"], "api_key", settings)
    assert client.count("connector_secrets") == 3  # 450 ids / 200 per chunk
    assert set(out) == set(ids)
    for i, cid in enumerate(ids):
        assert out[cid] == (f"v-{cid}" if i % 3 == 0 else None)


def test_get_decrypted_secrets_bulk_no_ids_issues_no_query(settings) -> None:
    client = _Client({})
    assert get_decrypted_secrets_bulk(client, [], "api_key", settings) == {}
    assert client.executions == []
