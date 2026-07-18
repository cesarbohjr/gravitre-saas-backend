"""Portal-aware HubSpot deep-link helpers."""
from app.services.hubspot_urls import (
    contacts_object_list_url,
    extract_hub_id,
    is_portal_scoped_hubspot_url,
    record_url,
    resolve_search_or_list_result_url,
)


def test_extract_hub_id_from_config_and_tokens() -> None:
    assert extract_hub_id({"hub_id": "123456"}) == "123456"
    assert extract_hub_id({"config": {"portalId": 99}}) == "99"
    assert extract_hub_id({"hubId": None}, {"hub_id": "42"}) == "42"
    assert extract_hub_id({}) is None


def test_never_emit_portal_less_list_url() -> None:
    assert contacts_object_list_url(None) is None
    assert contacts_object_list_url("") is None
    url = contacts_object_list_url("123456")
    assert url == "https://app.hubspot.com/contacts/123456/objects/0-1/views/all/list"
    assert is_portal_scoped_hubspot_url(url)
    assert not is_portal_scoped_hubspot_url(
        "https://app.hubspot.com/contacts/objects/0-1/views/all/list"
    )


def test_zero_results_omit_result_url() -> None:
    assert resolve_search_or_list_result_url("123", object_type="contacts", records=[]) is None
    assert resolve_search_or_list_result_url("123", object_type="contacts", records=None) is None


def test_single_record_prefers_record_url() -> None:
    url = resolve_search_or_list_result_url(
        "123",
        object_type="contacts",
        records=[{"id": "99"}],
    )
    assert url == record_url("123", object_type="contacts", record_id="99")
