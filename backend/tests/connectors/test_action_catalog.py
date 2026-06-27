"""Connector action catalog — v1/v2/v3 tools and demo workflows."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog import (
    connector_actions_for_goal_service,
    demo_workflows_for_vendor,
    get_vendor_catalog_dict,
    get_vendor_spec,
    list_catalog_vendors,
    list_full_catalog,
    read_tools_for_vendor,
)
from app.services.goal_service import CONNECTOR_ACTIONS
from app.services.tool_service import list_registered_actions


@pytest.fixture(scope="module")
def catalog() -> dict:
    return list_full_catalog()


def test_catalog_covers_all_vendors(catalog: dict) -> None:
    vendors = {v["vendor"] for v in catalog["vendors"]}
    assert len(vendors) >= 57
    assert "hubspot" in vendors
    assert "salesforce" in vendors
    assert "mailchimp" in vendors


def test_each_vendor_has_three_tiers_and_four_workflows(catalog: dict) -> None:
    for entry in catalog["vendors"]:
        tiers = entry["tiers"]
        assert len(tiers["v1"]["actions"]) >= 1, entry["vendor"]
        assert len(tiers["v2"]["actions"]) >= 1, entry["vendor"]
        assert len(tiers["v3"]["actions"]) >= 1, entry["vendor"]
        assert len(entry["demoWorkflows"]) == 4, entry["vendor"]
        assert len(entry["readTools"]) >= 1, entry["vendor"]


def test_hubspot_v1_read_tools_implemented(catalog: dict) -> None:
    hubspot = next(v for v in catalog["vendors"] if v["vendor"] == "hubspot")
    implemented_reads = [a for a in hubspot["tiers"]["v1"]["actions"] if a["implemented"]]
    tools = {a["tool"] for a in implemented_reads}
    assert "hubspot.contacts.get" in tools
    assert "hubspot.contacts.search" in tools


def test_constant_contact_catalog_actions_implemented(catalog: dict) -> None:
    cc = next(v for v in catalog["vendors"] if v["vendor"] == "constant_contact")
    registered = set(list_registered_actions())
    for tier in ("v1", "v2", "v3", "v4"):
        assert tier in cc["tiers"], f"missing tier {tier}"
        for action in cc["tiers"][tier]["actions"]:
            assert action["tool"] in registered
            assert action["implemented"] is True


def test_pipedrive_catalog_actions_implemented(catalog: dict) -> None:
    pipedrive = next(v for v in catalog["vendors"] if v["vendor"] == "pipedrive")
    registered = set(list_registered_actions())
    for tier in ("v1", "v2", "v3"):
        assert tier in pipedrive["tiers"], f"missing tier {tier}"
        for action in pipedrive["tiers"][tier]["actions"]:
            assert action["tool"] in registered
            assert action["implemented"] is True


def test_clickup_catalog_actions_implemented(catalog: dict) -> None:
    clickup = next(v for v in catalog["vendors"] if v["vendor"] == "clickup")
    registered = set(list_registered_actions())
    for tier in ("v1", "v2", "v3", "v4"):
        for action in clickup["tiers"][tier]["actions"]:
            assert action["tool"] in registered
            assert action["implemented"] is True


def test_intercom_catalog_actions_implemented(catalog: dict) -> None:
    intercom = next(v for v in catalog["vendors"] if v["vendor"] == "intercom")
    registered = set(list_registered_actions())
    for tier in ("v1", "v2", "v3", "v4"):
        for action in intercom["tiers"][tier]["actions"]:
            assert action["tool"] in registered
            assert action["implemented"] is True


def test_hubspot_v4_actions_implemented(catalog: dict) -> None:
    hubspot = next(v for v in catalog["vendors"] if v["vendor"] == "hubspot")
    assert "v4" in hubspot["tiers"]
    registered = set(list_registered_actions())
    for action in hubspot["tiers"]["v4"]["actions"]:
        assert action["tool"] in registered
        assert action["implemented"] is True


def test_tier3_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    for vendor in ("asana", "monday", "clickup"):
        entry = next(v for v in catalog["vendors"] if v["vendor"] == vendor)
        assert entry["shipped"] is True
        for tier in ("v1", "v2", "v3", "v4"):
            tier_block = entry["tiers"].get(tier)
            if not tier_block:
                continue
            for action in tier_block["actions"]:
                assert action["tool"] in registered, f"{vendor} missing {action['tool']}"
                assert action["implemented"] is True


def test_tier2_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    for vendor in ("quickbooks", "netsuite"):
        entry = next(v for v in catalog["vendors"] if v["vendor"] == vendor)
        assert entry["shipped"] is True
        for tier in ("v1", "v2", "v3"):
            for action in entry["tiers"][tier]["actions"]:
                assert action["tool"] in registered, f"{vendor} missing {action['tool']}"
                assert action["implemented"] is True


def test_odoo_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "odoo")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"odoo missing {action['tool']}"
            assert action["implemented"] is True


def test_github_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "github")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"github missing {action['tool']}"
            assert action["implemented"] is True


def test_canva_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "canva")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"canva missing {action['tool']}"
            assert action["implemented"] is True


def test_figma_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "figma")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"figma missing {action['tool']}"
            assert action["implemented"] is True


def test_apollo_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "apollo")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"apollo missing {action['tool']}"
            assert action["implemented"] is True


def test_microsoft365_catalog_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "microsoft365")
    assert entry["shipped"] is True
    for tier in ("v1", "v2", "v3", "v4"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"microsoft365 missing {action['tool']}"
            assert action["implemented"] is True


def test_microsoft_teams_legacy_actions_implemented(catalog: dict) -> None:
    registered = set(list_registered_actions())
    entry = next(v for v in catalog["vendors"] if v["vendor"] == "microsoft_teams")
    for tier in ("v1", "v2", "v3"):
        for action in entry["tiers"][tier]["actions"]:
            assert action["tool"] in registered, f"microsoft_teams missing {action['tool']}"
            assert action["implemented"] is True


def test_implemented_flag_matches_registry(catalog: dict) -> None:
    registered = set(list_registered_actions())
    hubspot = next(v for v in catalog["vendors"] if v["vendor"] == "hubspot")
    for tier in ("v1", "v2", "v3"):
        for action in hubspot["tiers"][tier]["actions"]:
            if action["tool"] in registered:
                assert action["implemented"] is True


def test_goal_service_uses_catalog() -> None:
    assert "hubspot" in CONNECTOR_ACTIONS
    assert "contacts_get" in CONNECTOR_ACTIONS["hubspot"] or "contacts.get" in str(CONNECTOR_ACTIONS["hubspot"])


def test_demo_workflow_shapes() -> None:
    workflows = demo_workflows_for_vendor("stripe")
    assert len(workflows) == 4
    assert workflows[0]["id"] == "stripe-inbound-triage"
    assert any(step["type"] == "invoke_tool" for step in workflows[0]["steps"])


def test_read_tools_for_vendor() -> None:
    reads = read_tools_for_vendor("jira")
    assert "jira.issues.get" in reads


def test_unknown_vendor_returns_none() -> None:
    assert get_vendor_spec("not_a_vendor") is None
    assert get_vendor_catalog_dict("not_a_vendor") is None


def test_connector_actions_for_goal_service_keys() -> None:
    actions = connector_actions_for_goal_service()
    assert len(actions) == len(list_catalog_vendors())
