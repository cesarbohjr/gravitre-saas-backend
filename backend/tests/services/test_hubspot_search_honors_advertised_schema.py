"""HubSpot search executors must accept the calls their own schema invites.

The catalog advertises hubspot.*.search with `required: []` and an optional
`query`. A model following that schema sends `query` alone, or no criteria at
all. Both used to raise ToolValidationError ("requires filter_groups array"),
so an ordinary read question intermittently dead-ended depending on whether the
model happened to pick `deals.search` or `deals.list` for the same request.

These tests pin the contract in both directions: the advertised shapes work, and
an explicit filter is still passed through to the vendor untouched.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.action_catalog.action_parameters import ACTION_PARAMETERS
from app.services.tool_service import (
    _exec_hubspot_companies_search,
    _exec_hubspot_contacts_search,
    _exec_hubspot_deals_search,
    _exec_hubspot_tickets_search,
    _resolve_hubspot_search,
)
from app.services.tool_types import ToolContext

SEARCH_CASES = [
    ("hubspot.deals.search", _exec_hubspot_deals_search, "deals", "dealname"),
    ("hubspot.contacts.search", _exec_hubspot_contacts_search, "contacts", "email"),
    ("hubspot.companies.search", _exec_hubspot_companies_search, "companies", "name"),
    ("hubspot.tickets.search", _exec_hubspot_tickets_search, "tickets", "subject"),
]


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False, private_connector_runtime_enabled=False),
        client=MagicMock(),
        org_id="11111111-1111-1111-1111-111111111111",
        actor_id="user-1",
        environment_name="production",
    )


@pytest.fixture
def hubspot_calls():
    """Record which vendor endpoint each executor reaches."""
    calls: dict[str, list[dict]] = {}

    def recorder(name):
        def _fn(_token=None, **kwargs):
            calls.setdefault(name, []).append(kwargs)
            return {"results": [{"id": "1", "properties": {}}], "total": 1}

        return _fn

    targets = {
        "search_deals": "deals",
        "list_deals": "deals",
        "search_contacts": "contacts",
        "list_contacts": "contacts",
        "search_companies": "companies",
        "list_companies": "companies",
        "search_tickets": "tickets",
        "list_tickets": "tickets",
    }
    # HubSpot's list_tickets is imported under an alias because app.connectors
    # .zendesk exports the same name and is imported later.
    patch_attr = {"list_tickets": "hubspot_list_tickets"}
    with patch(
        "app.services.tool_service._hubspot_connector_and_token",
        return_value=("conn-hs", "token-hs"),
    ), patch("app.services.tool_service._hubspot_hub_id", return_value="1234567"):
        stack = []
        for fn in targets:
            attr = patch_attr.get(fn, fn)
            p = patch(f"app.services.tool_service.{attr}", side_effect=recorder(fn))
            p.start()
            stack.append(p)
        try:
            yield calls
        finally:
            for p in stack:
                p.stop()


# --- the advertised schema is what we must honour -------------------------


@pytest.mark.parametrize("action,_exec,_obj,_prop", SEARCH_CASES)
def test_schema_advertises_no_required_fields_and_an_optional_query(action, _exec, _obj, _prop):
    """If this ever changes, the executor contract below must change with it."""
    schema = ACTION_PARAMETERS[action]
    assert schema.get("required") == [], f"{action} advertises required fields"
    assert "query" in schema["properties"], f"{action} advertises no query param"


# --- criteria-less search: the exact production failure ------------------


@pytest.mark.parametrize("action,executor,obj,_prop", SEARCH_CASES)
def test_search_with_no_criteria_serves_the_list_instead_of_dead_ending(
    action, executor, obj, _prop, hubspot_calls
):
    result = executor(_ctx(), {})
    assert result.success is True
    assert hubspot_calls.get(f"list_{obj}"), f"{action} did not fall back to the list endpoint"
    assert not hubspot_calls.get(f"search_{obj}"), f"{action} called search with no filters"


# --- query alone: what the schema explicitly invites ---------------------


@pytest.mark.parametrize("action,executor,obj,prop", SEARCH_CASES)
def test_query_alone_builds_the_vendor_filter_the_schema_promises(
    action, executor, obj, prop, hubspot_calls
):
    result = executor(_ctx(), {"query": "acme"})
    assert result.success is True
    sent = hubspot_calls.get(f"search_{obj}")
    assert sent, f"{action} did not reach the vendor search endpoint"
    groups = sent[0]["filter_groups"]
    filters = [f for g in groups for f in g["filters"]]
    assert any(f["propertyName"] == prop for f in filters), f"{action} ignored query for {prop}"
    assert all(f["value"] == "acme" for f in filters)
    assert all(f["operator"] == "CONTAINS_TOKEN" for f in filters)


# --- explicit filters still pass through untouched -----------------------


@pytest.mark.parametrize("action,executor,obj,_prop", SEARCH_CASES)
def test_explicit_filter_groups_reach_the_vendor_unchanged(
    action, executor, obj, _prop, hubspot_calls
):
    explicit = [{"filters": [{"propertyName": "hs_object_id", "operator": "EQ", "value": "42"}]}]
    result = executor(_ctx(), {"filter_groups": explicit})
    assert result.success is True
    sent = hubspot_calls.get(f"search_{obj}")
    assert sent and sent[0]["filter_groups"] == explicit
    assert not hubspot_calls.get(f"list_{obj}"), f"{action} downgraded a real filter to a list"


# --- the resolver itself -------------------------------------------------


def test_resolver_returns_none_only_when_there_is_genuinely_no_criteria():
    assert _resolve_hubspot_search("deals", {}) is None
    assert _resolve_hubspot_search("deals", {"query": "   "}) is None
    assert _resolve_hubspot_search("deals", {"filter_groups": []}) is None
    assert _resolve_hubspot_search("deals", {"limit": 25}) is None


def test_resolver_prefers_explicit_filters_over_query():
    explicit = [{"filters": [{"propertyName": "amount", "operator": "GT", "value": "1"}]}]
    got = _resolve_hubspot_search("deals", {"filter_groups": explicit, "query": "acme"})
    assert got == explicit


def test_resolver_accepts_the_camelcase_alias_hubspot_callers_use():
    explicit = [{"filters": [{"propertyName": "amount", "operator": "GT", "value": "1"}]}]
    assert _resolve_hubspot_search("deals", {"filterGroups": explicit}) == explicit


def test_contacts_free_text_searches_every_advertised_property():
    groups = _resolve_hubspot_search("contacts", {"query": "jane"})
    props = {f["propertyName"] for g in groups for f in g["filters"]}
    assert {"email", "firstname", "lastname", "company"} <= props


def test_list_all_still_wins_for_contacts():
    """The pre-existing escape hatch must keep working."""
    with patch(
        "app.services.tool_service._hubspot_connector_and_token",
        return_value=("conn-hs", "token-hs"),
    ), patch("app.services.tool_service._hubspot_hub_id", return_value="1234567"), patch(
        "app.services.tool_service.list_contacts", return_value={"results": []}
    ) as lister, patch(
        "app.services.tool_service.search_contacts"
    ) as searcher:
        res = _exec_hubspot_contacts_search(_ctx(), {"list_all": True, "query": "jane"})
    assert res.success is True
    lister.assert_called_once()
    searcher.assert_not_called()
