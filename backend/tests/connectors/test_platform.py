"""Connector platform helpers (OAuth reuse, API key storage)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.connectors.platform import (
    clear_connector_oauth_tokens,
    find_existing_oauth_connector,
    mark_connector_pending_oauth,
    oauth_docs_url,
    prepare_oauth_connector,
    store_connector_api_key,
)


def test_oauth_docs_url_known_vendors():
    assert "hubspot.com" in oauth_docs_url("hubspot")
    assert "salesforce.com" in oauth_docs_url("salesforce")
    assert "atlassian.com" in oauth_docs_url("confluence")


def test_find_existing_by_vendor():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    chain = client.table.return_value.select.return_value
    chain.eq.return_value.eq.return_value.is_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    by_vendor = chain.eq.return_value.eq.return_value.is_.return_value.order.return_value.limit.return_value
    by_vendor.execute.return_value = MagicMock(
        data=[{"id": "c1", "vendor": "hubspot", "name": "hubspot", "status": "pending_auth"}]
    )
    row = find_existing_oauth_connector(client, "org-1", "hubspot", "hubspot")
    assert row is not None
    assert row["id"] == "c1"


def test_prepare_oauth_reuses_existing():
    client = MagicMock()
    existing = {"id": "c1", "vendor": "hubspot", "name": "hubspot", "status": "healthy"}
    with patch("app.connectors.platform.find_existing_oauth_connector", return_value=existing):
        with patch("app.connectors.platform.mark_connector_pending_oauth") as mark:
            cid, reconnect, is_new = prepare_oauth_connector(
                client, org_id="org-1", vendor="hubspot", name="hubspot", environment_name="production"
            )
    assert cid == "c1"
    assert reconnect is True  # prior connected state
    assert is_new is False
    mark.assert_called_once()


def test_mark_pending_oauth_clears_stale_tokens():
    client = MagicMock()
    with patch("app.connectors.platform.clear_connector_oauth_tokens") as clear:
        mark_connector_pending_oauth(
            client,
            org_id="org-1",
            connector_id="c1",
            vendor="hubspot",
            environment_name="production",
        )
    clear.assert_called_once_with(client, "c1")
    client.table.return_value.update.assert_called_once()
    payload = client.table.return_value.update.call_args.args[0]
    assert payload["status"] == "pending_auth"
    assert payload["deleted_at"] is None


def test_clear_connector_oauth_tokens_deletes_secret_row():
    client = MagicMock()
    clear_connector_oauth_tokens(client, "c1")
    client.table.assert_called_with("connector_secrets")
    client.table.return_value.delete.assert_called_once()


def test_prepare_oauth_recovers_soft_deleted_name_conflict():
    client = MagicMock()
    insert_exc = Exception(
        'duplicate key value violates unique constraint "connectors_org_name_key" (23505)'
    )
    client.table.return_value.insert.return_value.execute.side_effect = insert_exc
    with patch("app.connectors.platform.find_existing_oauth_connector", return_value=None):
        with patch(
            "app.connectors.platform._fetch_connector_by_org_name",
            return_value={
                "id": "c-slack",
                "vendor": "slack",
                "name": "slack",
                "status": "disconnected",
                "deleted_at": "2026-06-01T00:00:00Z",
            },
        ):
            with patch("app.connectors.platform.mark_connector_pending_oauth") as mark:
                cid, reconnect, is_new = prepare_oauth_connector(
                    client, org_id="org-1", vendor="slack", name="slack", environment_name="production"
                )
    assert cid == "c-slack"
    assert reconnect is False
    assert is_new is False
    mark.assert_called_once()


def test_store_api_key_uses_connector_secrets():
    client = MagicMock()
    settings = SimpleNamespace(
        connector_secrets_encryption_key="a" * 64,
        encryption_key="",
    )
    with patch("app.connectors.platform.set_secret") as set_secret:
        result = store_connector_api_key(client, "org", "conn", "sk_test_123", settings)
    assert result is None
    set_secret.assert_called_once()


def test_store_api_key_requires_encryption():
    client = MagicMock()
    settings = SimpleNamespace(connector_secrets_encryption_key="", encryption_key="")
    with pytest.raises(HTTPException) as exc:
        store_connector_api_key(client, "org", "conn", "key", settings)
    assert exc.value.status_code == 503


def test_prepare_oauth_type_check_error():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = Exception(
        'new row violates check constraint "connectors_type_check" (23514)'
    )
    with patch("app.connectors.platform.find_existing_oauth_connector", return_value=None):
        with pytest.raises(HTTPException) as exc:
            prepare_oauth_connector(
                client, org_id="org-1", vendor="figma", name="figma", environment_name="production"
            )
    assert exc.value.status_code == 503
    detail = exc.value.detail
    if isinstance(detail, dict):
        assert detail.get("code") == "CONNECTOR_TYPE_SCHEMA_OUTDATED"
