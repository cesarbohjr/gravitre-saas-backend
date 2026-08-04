from __future__ import annotations

from types import SimpleNamespace

from app.connectors.google_analytics_oauth import (
    google_analytics_authorize_url,
    google_analytics_oauth_configured,
    google_analytics_redirect_uri,
    link_ga4_property,
    normalize_vendor,
)


def test_normalize_vendor_google_analytics():
    assert normalize_vendor("Google Analytics") == "google_analytics"
    assert normalize_vendor("ga4") == "google_analytics"


def test_google_analytics_oauth_configured():
    settings = SimpleNamespace(
        google_analytics_client_id="cid",
        google_analytics_client_secret="sec",
    )
    assert google_analytics_oauth_configured(settings) is True
    assert google_analytics_oauth_configured(SimpleNamespace(
        google_analytics_client_id="",
        google_analytics_client_secret="",
    )) is False


def test_google_analytics_redirect_and_authorize():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = google_analytics_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/google/callback"
    url = google_analytics_authorize_url("cid", redirect, "state123")
    assert "accounts.google.com" in url
    assert "analytics.readonly" in url
    assert "access_type=offline" in url


def test_link_ga4_property_sets_connected_status():
    updates: list[dict] = []

    class _FakeQuery:
        def __init__(self, client, table):
            self._client = client
            self._table = table
            self._filters = {}
            self._payload = None

        def select(self, *_a, **_k):
            return self

        def eq(self, key, value):
            self._filters[key] = value
            return self

        def limit(self, *_a, **_k):
            return self

        def update(self, payload):
            self._payload = payload
            return self

        def execute(self):
            if self._payload is not None:
                updates.append(dict(self._payload))
                return SimpleNamespace(data=[])
            return SimpleNamespace(data=[{"config": {"oauth_provider": "google_analytics"}}])

    class _FakeClient:
        def table(self, name):
            return _FakeQuery(self, name)

    link_ga4_property(
        _FakeClient(),
        "org",
        "conn",
        property_id="545453247",
        property_name="Gravitre",
        property_resource="properties/545453247",
    )
    assert updates
    assert updates[0]["status"] == "connected"
    assert updates[0]["config"]["property_id"] == "545453247"
    assert updates[0]["config"]["health"]["authStatus"] == "connected"
