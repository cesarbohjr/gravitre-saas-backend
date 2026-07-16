from __future__ import annotations

from app.connectors.hubspot_oauth import (
    hubspot_authorize_url,
    normalize_vendor,
)


def test_normalize_vendor_hubspot():
    assert normalize_vendor("HubSpot") == "hubspot"
    assert normalize_vendor("hubspot") == "hubspot"


def test_hubspot_authorize_url_contains_params():
    from urllib.parse import parse_qs, urlparse

    url = hubspot_authorize_url("client-id", "https://api.example.com/callback", "state-xyz")
    assert "app.hubspot.com/oauth/authorize" in url
    assert "client-id" in url
    assert "state-xyz" in url
    qs = parse_qs(urlparse(url).query)
    required = (qs.get("scope") or [""])[0]
    optional = (qs.get("optional_scope") or [""])[0]
    assert "crm.objects.contacts.read" in required
    assert "crm.objects.companies.read" in required
    assert "tickets" not in required.split()
    assert "tickets" in optional.split()
    assert "automation" in optional
    assert "crm.objects.companies.write" in optional
    assert "crm.objects.owners.read" in optional
