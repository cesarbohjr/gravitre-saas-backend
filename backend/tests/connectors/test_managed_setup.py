from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.connectors.managed_setup import provider_readiness, managed_setup_catalog, integration_inventory, _cache
from app.connectors.nango_registry import get_nango_connector_spec


@pytest.mark.parametrize("inventory,expected", [
    ([], (False, "integration_missing")),
    ([{"key":"front","provider":"slack","missing_fields":[]}], (False,"provider_mismatch")),
    ([{"key":"front","provider":"front","missing_fields":["oauth_client_id"]}], (False,"provider_credentials_required")),
    ([{"key":"front","provider":"front","missing_fields":None}], (False,"provider_credentials_required")),
    ([{"key":"front","provider":"front","missing_fields":[]}], (True,None)),
])
def test_provider_readiness_requires_specific_matching_integration(inventory, expected):
    assert provider_readiness(get_nango_connector_spec("front"), inventory) == expected


def test_unknown_provider_mapping_is_not_available():
    assert provider_readiness(get_nango_connector_spec("syncro"), []) == (False,"provider_not_supported")


@pytest.mark.parametrize("vendor", ["freshservice", "crowdstrike", "sage_intacct"])
def test_non_interactive_credentials_never_count_as_user_oauth(vendor):
    spec = get_nango_connector_spec(vendor)
    assert provider_readiness(spec, [{"key": spec.integration_id, "provider": spec.provider, "missing_fields": []}]) == (False, "interactive_oauth_unavailable")


def test_catalog_fails_closed_during_nango_outage(monkeypatch):
    import app.connectors.managed_setup as setup
    monkeypatch.setattr(setup,"integration_inventory",MagicMock(side_effect=httpx.ConnectError("private details")))
    data=managed_setup_catalog(SimpleNamespace(nango_secret_key="s",nango_webhook_signing_key="w"))
    assert data["configured"] and not data["inventoryChecked"]
    assert all(not row["available"] and row["setupReason"]=="setup_check_unavailable" for row in data["connectors"])
    assert "private details" not in str(data)


def test_inventory_cache_is_key_scoped_and_drops_credentials(monkeypatch):
    _cache.clear()
    call=MagicMock(side_effect=lambda *a,**kw: httpx.Response(200,json={"data":[{
        "unique_key":"x","provider":"front","missing_fields":[],"credentials":{"client_secret":"never expose"}}]},
        request=httpx.Request("GET","https://api.nango.dev/integrations")))
    monkeypatch.setattr(httpx.Client,"get",call)
    one=SimpleNamespace(nango_secret_key="one",nango_api_base_url="https://api.nango.dev")
    two=SimpleNamespace(nango_secret_key="two",nango_api_base_url="https://api.nango.dev")
    assert "never expose" not in str(integration_inventory(one))
    integration_inventory(one); integration_inventory(two)
    assert call.call_count==2
    _cache.clear()

@pytest.mark.parametrize("vendor", ["instantly", "smartlead", "quickmail", "hunter", "snov", "emailable", "millionverifier"])
def test_api_key_connection_ready_only_when_nango_template_is_configured(vendor):
    spec = get_nango_connector_spec(vendor)
    ready, reason = provider_readiness(spec, [
        {"key": spec.integration_id, "provider": spec.provider, "missing_fields": []}
    ])
    assert (ready, reason) == (True, None)
    assert provider_readiness(spec, []) == (False, "integration_missing")
