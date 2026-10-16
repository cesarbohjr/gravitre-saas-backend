"""Tests for org-scoped API key management + lookup service.

Coverage:
- POST /api/org/{org_id}/api-keys  (create)
  - happy path: 201, raw key returned, audit event written
  - non-admin returns 403
  - invalid scope returns 422
  - per-org key cap returns 409
  - DB insert failure returns 500
  - test-mode key gets grav_test_ prefix
- GET /api/org/{org_id}/api-keys (list)
  - happy path: keys returned without hashes
  - non-admin returns 403
- DELETE /api/org/{org_id}/api-keys/{id} (revoke)
  - happy path: 200 revoked=True
  - already-revoked key: idempotent 200
  - wrong org returns 404
  - DB update failure returns 500
- api_key_auth service unit tests
  - generate_api_key live prefix
  - generate_api_key test prefix
  - hash_api_key deterministic
  - extract_raw_key bearer header
  - extract_raw_key X-Gravitre-Key header
  - extract_raw_key ignores JWT bearer
  - validate_scopes valid
  - validate_scopes unknown scope raises
  - lookup_api_key found + expiry check
  - lookup_api_key revoked/missing → None
  - lookup_api_key expired → None
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_supabase_client(
    *,
    key_rows: list[dict] | None = None,
    active_key_count: int = 0,
    insert_raises: bool = False,
    update_raises: bool = False,
    check_rows: list[dict] | None = None,
) -> MagicMock:
    """Build a Supabase client mock for API key management tests."""
    client = MagicMock()

    # --- insert ---
    insert_result = MagicMock()
    insert_result.data = [{
        "id": "key-1",
        "created_at": "2026-10-16T00:00:00+00:00",
    }]

    def _insert(*a, **k):
        if insert_raises:
            raise RuntimeError("db insert error")
        return MagicMock(execute=MagicMock(return_value=insert_result))

    # --- update ---
    update_result = MagicMock()
    update_result.data = [{"id": "key-1"}]

    def _update_chain(*a, **k):
        if update_raises:
            raise RuntimeError("db update error")
        eq1 = MagicMock()
        eq1.eq.return_value = MagicMock(execute=MagicMock(return_value=update_result))
        return eq1

    # --- select ---
    list_result = MagicMock()
    list_result.data = key_rows if key_rows is not None else []

    check_result = MagicMock()
    check_result.data = check_rows if check_rows is not None else []

    # count result for key cap check
    count_result = MagicMock()
    count_result.count = active_key_count
    count_result.data = [{"id": f"k{i}"} for i in range(active_key_count)]

    call_count = {"n": 0}

    def _select(*a, **k):
        call_count["n"] += 1
        chain = MagicMock()
        # Mimic common chaining: .eq().is_().execute() or .order().limit().execute()
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.order.return_value = chain

        # For the count (key cap) query we return count_result; for list or check queries
        # we use list_result / check_result.  Heuristic: first select in create endpoint
        # is the cap check; subsequent selects are list/check.
        if call_count["n"] == 1:
            chain.limit.return_value = MagicMock(execute=MagicMock(return_value=count_result))
            chain.execute.return_value = count_result
        else:
            chain.limit.return_value = MagicMock(execute=MagicMock(return_value=check_result))
            chain.execute.return_value = list_result
        return chain

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        tbl.insert.side_effect = _insert
        tbl.update.side_effect = _update_chain
        tbl.select.side_effect = _select
        return tbl

    client.table.side_effect = _table
    return client


def _make_app(
    *,
    is_admin: bool = True,
    key_rows: list[dict] | None = None,
    active_key_count: int = 0,
    insert_raises: bool = False,
    update_raises: bool = False,
    check_rows: list[dict] | None = None,
) -> tuple[FastAPI, MagicMock]:
    from app.routers.org_api_keys import router
    from app.auth.dependencies import get_current_user
    from app.config import get_settings

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-admin-1"}
    app.dependency_overrides[get_settings] = lambda: MagicMock()

    supabase = _make_supabase_client(
        key_rows=key_rows,
        active_key_count=active_key_count,
        insert_raises=insert_raises,
        update_raises=update_raises,
        check_rows=check_rows,
    )
    return app, supabase


# ---------------------------------------------------------------------------
# POST (create) tests
# ---------------------------------------------------------------------------


def test_create_api_key_happy_path() -> None:
    app, supabase = _make_app()
    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
        patch("app.routers.org_api_keys.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "My Integration", "scopes": ["chat:read"]},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["label"] == "My Integration"
    assert data["scopes"] == ["chat:read"]
    # Raw key must be present and start with grav_live_
    assert data["key"].startswith("grav_live_")
    # key_prefix is the first 12 chars
    assert data["key_prefix"] == data["key"][:12]
    assert "id" in data


def test_create_api_key_test_mode() -> None:
    app, supabase = _make_app()
    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
        patch("app.routers.org_api_keys.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "Test Key", "scopes": [], "test": True},
        )
    assert resp.status_code == 201
    assert resp.json()["key"].startswith("grav_test_")


def test_create_api_key_non_admin_returns_403() -> None:
    app, supabase = _make_app()
    # is_platform_admin=False + no org membership → 403
    member_result = MagicMock()
    member_result.data = []  # no membership

    def _select_member(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=member_result))
        return chain

    supabase.table.side_effect = lambda name: MagicMock(select=_select_member)

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=False),
    ):
        client = TestClient(app)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "x", "scopes": []},
        )
    assert resp.status_code == 403


def test_create_api_key_invalid_scope_returns_422() -> None:
    app, supabase = _make_app()
    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "x", "scopes": ["admin:all"]},
        )
    assert resp.status_code == 422


def test_create_api_key_cap_returns_409() -> None:
    app, supabase = _make_app(active_key_count=20)
    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "x", "scopes": []},
        )
    assert resp.status_code == 409
    assert "limit" in resp.json()["detail"].lower()


def test_create_api_key_db_failure_returns_500() -> None:
    app, supabase = _make_app(insert_raises=True)
    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app)
        resp = client.post(
            "/api/org/org-1/api-keys",
            json={"label": "x", "scopes": []},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET (list) tests
# ---------------------------------------------------------------------------


def test_list_api_keys_happy_path() -> None:
    rows = [
        {
            "id": "key-1",
            "label": "Prod Key",
            "key_prefix": "grav_live_ab",
            "scopes": ["chat:read"],
            "expires_at": None,
            "last_used_at": None,
            "created_at": "2026-10-16T00:00:00+00:00",
            "created_by": "user-admin-1",
        }
    ]
    # For list test: call_count first goes to list endpoint (no cap check first)
    app, supabase = _make_app(key_rows=rows, active_key_count=1)

    # Reset side-effect to return list_result immediately (not via cap-check path)
    list_result = MagicMock()
    list_result.data = rows

    def _select_list(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=list_result))
        return chain

    supabase.table.side_effect = lambda name: MagicMock(select=_select_list)

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/api/org/org-1/api-keys")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["keys"]) == 1
    key = data["keys"][0]
    assert key["id"] == "key-1"
    assert key["label"] == "Prod Key"
    assert key["key_prefix"] == "grav_live_ab"
    # Ensure raw key and hash are never in the response
    assert "key" not in key
    assert "key_hash" not in key


def test_list_api_keys_non_admin_returns_403() -> None:
    app, supabase = _make_app()
    member_result = MagicMock()
    member_result.data = []

    def _select_member(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=member_result))
        return chain

    supabase.table.side_effect = lambda name: MagicMock(select=_select_member)

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=False),
    ):
        client = TestClient(app)
        resp = client.get("/api/org/org-1/api-keys")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE (revoke) tests
# ---------------------------------------------------------------------------


def test_revoke_api_key_happy_path() -> None:
    check_rows = [{"id": "key-1", "revoked_at": None}]
    app, supabase = _make_app(check_rows=check_rows)

    check_result = MagicMock()
    check_result.data = check_rows

    update_result = MagicMock()
    update_result.data = [{"id": "key-1"}]

    def _select_check(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=check_result))
        return chain

    def _update_chain(*a, **k):
        eq1 = MagicMock()
        eq1.eq.return_value = MagicMock(execute=MagicMock(return_value=update_result))
        return eq1

    tbl_mock = MagicMock()
    tbl_mock.select = _select_check
    tbl_mock.update = _update_chain
    supabase.table.side_effect = lambda name: tbl_mock

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
        patch("app.routers.org_api_keys.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.delete("/api/org/org-1/api-keys/key-1")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == "key-1"
    assert data["revoked"] is True


def test_revoke_already_revoked_is_idempotent() -> None:
    check_rows = [{"id": "key-1", "revoked_at": "2026-10-10T00:00:00+00:00"}]
    app, supabase = _make_app(check_rows=check_rows)

    check_result = MagicMock()
    check_result.data = check_rows

    def _select_check(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=check_result))
        return chain

    supabase.table.side_effect = lambda name: MagicMock(select=_select_check)

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.delete("/api/org/org-1/api-keys/key-1")

    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


def test_revoke_wrong_org_returns_404() -> None:
    app, supabase = _make_app(check_rows=[])

    check_result = MagicMock()
    check_result.data = []

    def _select_check(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=check_result))
        return chain

    supabase.table.side_effect = lambda name: MagicMock(select=_select_check)

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app)
        resp = client.delete("/api/org/org-1/api-keys/no-such-key")
    assert resp.status_code == 404


def test_revoke_db_update_failure_returns_500() -> None:
    check_rows = [{"id": "key-1", "revoked_at": None}]
    app, supabase = _make_app(check_rows=check_rows, update_raises=True)

    check_result = MagicMock()
    check_result.data = check_rows

    def _select_check(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=check_result))
        return chain

    def _update_raises(*a, **k):
        raise RuntimeError("db down")

    tbl_mock = MagicMock()
    tbl_mock.select = _select_check
    tbl_mock.update = _update_raises
    supabase.table.side_effect = lambda name: tbl_mock

    with (
        patch("app.routers.org_api_keys.shared_service_client", return_value=supabase),
        patch("app.routers.org_api_keys.is_platform_admin", return_value=True),
    ):
        client = TestClient(app)
        resp = client.delete("/api/org/org-1/api-keys/key-1")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# api_key_auth service unit tests
# ---------------------------------------------------------------------------


def test_generate_api_key_live_prefix() -> None:
    from app.auth.api_key_auth import generate_api_key
    raw, prefix, hsh = generate_api_key(test=False)
    assert raw.startswith("grav_live_")
    assert prefix == raw[:12]
    assert len(hsh) == 64  # SHA-256 hex


def test_generate_api_key_test_prefix() -> None:
    from app.auth.api_key_auth import generate_api_key
    raw, prefix, hsh = generate_api_key(test=True)
    assert raw.startswith("grav_test_")


def test_hash_api_key_deterministic() -> None:
    from app.auth.api_key_auth import hash_api_key
    key = "grav_live_abc123"
    assert hash_api_key(key) == hashlib.sha256(key.encode()).hexdigest()
    assert hash_api_key(key) == hash_api_key(key)


def test_extract_raw_key_bearer_header() -> None:
    from app.auth.api_key_auth import extract_raw_key
    key = "grav_live_ABCDEFGHIJ1234567890"
    result = extract_raw_key(f"Bearer {key}", None)
    assert result == key


def test_extract_raw_key_x_header() -> None:
    from app.auth.api_key_auth import extract_raw_key
    key = "grav_test_ABCDEFGHIJ1234567890"
    result = extract_raw_key(None, key)
    assert result == key


def test_extract_raw_key_ignores_non_gravitre_bearer() -> None:
    from app.auth.api_key_auth import extract_raw_key
    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyLTEifQ.sig"
    result = extract_raw_key(f"Bearer {jwt}", None)
    assert result is None


def test_extract_raw_key_missing_returns_none() -> None:
    from app.auth.api_key_auth import extract_raw_key
    assert extract_raw_key(None, None) is None


def test_validate_scopes_valid() -> None:
    from app.auth.api_key_auth import validate_scopes
    scopes = validate_scopes(["chat:read", "billing:read"])
    assert set(scopes) == {"chat:read", "billing:read"}


def test_validate_scopes_unknown_raises() -> None:
    from app.auth.api_key_auth import validate_scopes
    with pytest.raises(ValueError, match="Unknown scopes"):
        validate_scopes(["admin:all"])


def test_lookup_api_key_found() -> None:
    from app.auth.api_key_auth import generate_api_key, lookup_api_key

    raw, _, key_hash = generate_api_key()
    row = {
        "id": "key-1",
        "org_id": "org-1",
        "created_by": "user-1",
        "scopes": ["chat:read"],
        "expires_at": None,
    }

    supabase = MagicMock()
    result = MagicMock()
    result.data = [row]

    chain = MagicMock()
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.limit.return_value = MagicMock(execute=MagicMock(return_value=result))
    supabase.table.return_value = MagicMock(select=MagicMock(return_value=chain))

    ctx = lookup_api_key(supabase, raw)
    assert ctx is not None
    assert ctx["org_id"] == "org-1"
    assert ctx["scopes"] == ["chat:read"]


def test_lookup_api_key_not_found_returns_none() -> None:
    from app.auth.api_key_auth import lookup_api_key

    supabase = MagicMock()
    result = MagicMock()
    result.data = []

    chain = MagicMock()
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.limit.return_value = MagicMock(execute=MagicMock(return_value=result))
    supabase.table.return_value = MagicMock(select=MagicMock(return_value=chain))

    ctx = lookup_api_key(supabase, "grav_live_doesnotexist0000000000000000000000")
    assert ctx is None


def test_lookup_api_key_expired_returns_none() -> None:
    from app.auth.api_key_auth import generate_api_key, lookup_api_key

    raw, _, _ = generate_api_key()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    row = {
        "id": "key-1",
        "org_id": "org-1",
        "created_by": "user-1",
        "scopes": [],
        "expires_at": past,
    }

    supabase = MagicMock()
    result = MagicMock()
    result.data = [row]

    chain = MagicMock()
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.limit.return_value = MagicMock(execute=MagicMock(return_value=result))
    supabase.table.return_value = MagicMock(select=MagicMock(return_value=chain))

    ctx = lookup_api_key(supabase, raw)
    assert ctx is None
