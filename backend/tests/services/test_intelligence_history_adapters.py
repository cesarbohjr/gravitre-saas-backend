from app.services.intelligence_history_adapters import (
    HistoricalProviderAdapter, authorized_history_object,
)


def test_hubspot_nested_record_normalizes_and_pages():
    requests = []
    def transport(kind, cursor, limit):
        requests.append((kind, cursor, limit))
        return {"records": [{"id": 123, "properties": {
            "email": "Contact@Example.com", "domain": "Example.com"}}], "next_cursor": None}
    adapter = HistoricalProviderAdapter("hubspot", transport)
    page = adapter.fetch_page("contact", {}, 100)
    assert page["records"][0]["id"] == "123"
    assert page["records"][0]["email"] == "Contact@Example.com"
    assert requests == [("contact", {}, 100)]


def test_provider_types_denied_before_transport():
    calls = []
    adapter = HistoricalProviderAdapter("stripe", lambda *a: calls.append(a))
    import pytest
    with pytest.raises(ValueError):
        adapter.fetch_page("contact", {}, 10)
    assert calls == []


def test_historical_scopes_require_explicit_consent_and_verified_grant():
    connector = {"type": "hubspot", "config": {"history_sync_enabled": True},
                 "verified_read_capabilities": ["contacts.read"]}
    assert authorized_history_object(connector, "contact")
    assert not authorized_history_object(connector, "deal")
    assert not authorized_history_object({**connector, "config": {}}, "contact")
    assert not authorized_history_object({**connector, "verified_read_capabilities": []}, "contact")
