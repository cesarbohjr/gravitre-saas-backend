"""Odoo API key connector tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.connectors.odoo import (
    OdooAPIError,
    infer_database_name,
    normalize_odoo_url,
    resolve_odoo_credentials,
    verify_odoo_credentials,
)
from app.config import Settings


def test_normalize_odoo_url_adds_https():
    assert normalize_odoo_url("company.odoo.com") == "https://company.odoo.com"


def test_infer_database_from_odoo_saas_host():
    assert infer_database_name("https://acme.odoo.com") == "acme"


def test_infer_database_requires_explicit_for_self_hosted():
    with pytest.raises(OdooAPIError):
        infer_database_name("https://erp.example.com")


@patch("app.connectors.odoo.get_decrypted_secret")
@patch("app.connectors.odoo.get_connector_by_type")
def test_resolve_odoo_credentials(mock_get_by_type, mock_secret):
    mock_get_by_type.return_value = {
        "id": "conn-1",
        "config": {"odoo_url": "https://acme.odoo.com"},
    }
    mock_secret.side_effect = lambda _client, _cid, key, _settings: {
        "username": "admin@acme.com",
        "api_key": "odoo-key",
    }.get(key)

    settings = Settings(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
    )
    cid, base, db, user, key = resolve_odoo_credentials(MagicMock(), "org", None, settings)
    assert cid == "conn-1"
    assert base == "https://acme.odoo.com"
    assert db == "acme"
    assert user == "admin@acme.com"
    assert key == "odoo-key"


@patch("app.connectors.odoo._jsonrpc")
def test_verify_odoo_credentials_authenticates(mock_jsonrpc):
    mock_jsonrpc.return_value = 42
    uid = verify_odoo_credentials("https://acme.odoo.com", "acme", "admin@acme.com", "odoo-key")
    assert uid == 42
    mock_jsonrpc.assert_called_once()


@patch("app.connectors.odoo.execute_kw")
def test_create_partner(mock_execute_kw):
    from app.connectors.odoo import create_partner

    mock_execute_kw.side_effect = [7, [{"id": 7, "name": "Acme", "email": "a@acme.com", "phone": False, "company_type": "company"}]]
    data = create_partner("https://acme.odoo.com", "acme", 1, "key", {"name": "Acme", "email": "a@acme.com"})
    assert data["id"] == 7
    assert mock_execute_kw.call_count == 2


@patch("app.connectors.odoo.execute_kw")
def test_batch_upsert_partners(mock_execute_kw):
    from app.connectors.odoo import batch_upsert_partners

    mock_execute_kw.side_effect = [
        True,
        [{"id": 1, "name": "A", "email": "a@acme.com", "phone": False, "company_type": "person"}],
        2,
        [{"id": 2, "name": "B", "email": False, "phone": False, "company_type": "person"}],
    ]
    rows = batch_upsert_partners(
        "https://acme.odoo.com",
        "acme",
        1,
        "key",
        [{"id": 1, "email": "a@acme.com"}, {"name": "B"}],
    )
    assert len(rows) == 2
