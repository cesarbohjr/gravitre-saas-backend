from __future__ import annotations

from app.connectors.hubspot_oauth import (
    hubspot_authorize_url,
    normalize_vendor,
)


def test_normalize_vendor_hubspot():
    assert normalize_vendor("HubSpot") == "hubspot"
    assert normalize_vendor("hubspot") == "hubspot"


def test_hubspot_authorize_url_contains_params():
    url = hubspot_authorize_url("client-id", "https://api.example.com/callback", "state-xyz")
    assert "app.hubspot.com/oauth/authorize" in url
    assert "client-id" in url
    assert "state-xyz" in url
    assert "crm.objects.contacts.read" in url.replace("+", " ")
    assert "crm.objects.notes.write" in url.replace("+", " ")
    assert "optional_scope=automation" in url
