"""Connector platform helpers (OAuth reuse, API key storage)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.connectors.platform import (
    find_existing_oauth_connector,
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
