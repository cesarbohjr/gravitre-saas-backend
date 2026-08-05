"""F1 retrieve-before-generate + F3 list-create variance."""
from __future__ import annotations

from app.services.chat_action_mapper import ChatActionMapper
from app.services.chat_connector_models import LIST_CREATE_INTENT
from app.services.pack_common_intent_defaults import try_pack_common_list_create_plan
from app.services.retrieve_plan_gate import retrieve_plan_or_none
from app.services.unified_turn_classical_fallback import (
    message_requires_classical_tool_sse,
    should_defer_unified_turn_live_to_classical,
)


CONNECTED = ["apollo", "hubspot", "clay", "slack", "gmail"]

C2_LIST_PHRASINGS = [
    "Create a HubSpot static list named MSPs",
    "make me a new hubspot list called MSPs",
    "add a contact list MSPs in hubspot",
    "new apollo contact list for msp outreach",
    "can you set up a list MSPs on hubspot?",
    "I want a hubspot segment named MSPs",
    "create list",
    "spin up an outreach list in apollo for MSPs",
]


def test_f3_list_create_intent_covers_c2_verbs():
    for phrasing in C2_LIST_PHRASINGS:
        assert LIST_CREATE_INTENT.search(phrasing), phrasing


def test_f3_c2_probe_list_create_8_of_8():
    hits = 0
    for phrasing in C2_LIST_PHRASINGS:
        plan = try_pack_common_list_create_plan(
            phrasing, connected_integrations=CONNECTED
        )
        if plan is not None:
            hits += 1
    assert hits == 8, f"list-create C.2 probe expected 8/8, got {hits}/8"


def test_f1_msp_try_retrieves_not_none():
    try_prompt = (
        'Use Clay to enrich the existing Apollo contact list "MSP Prospects", '
        'then add those enriched contacts to the existing HubSpot static list "MSPs".'
    )
    retrieved = retrieve_plan_or_none(
        try_prompt,
        org_id="org",
        connected_integrations=CONNECTED,
        client=None,
    )
    assert retrieved is not None
    assert retrieved.kind == "pack_common_msp_enrich"
    assert retrieved.block_fabrication is True


def test_f1_ambiguous_enrich_my_list_clarifies():
    retrieved = retrieve_plan_or_none(
        "enrich my list with Clay and sync somewhere",
        org_id="org",
        connected_integrations=CONNECTED,
        client=None,
    )
    assert retrieved is not None
    assert retrieved.kind == "clarify"
    assert retrieved.block_fabrication is True


def test_f2_bare_apollo_slack_no_longer_force_defer():
    assert message_requires_classical_tool_sse("tell me about apollo pricing") is False
    assert message_requires_classical_tool_sse("is slack useful?") is False
    assert message_requires_classical_tool_sse("what is a contact list?") is False
    assert message_requires_classical_tool_sse("search the knowledge base") is False
    # Safety net still catches connector-status probes
    assert message_requires_classical_tool_sse(
        "What connectors are connected right now?"
    )


def test_f2_needs_tool_sse_drives_defer():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="anything",
        needs_tool_sse=True,
    )
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="hello",
        needs_tool_sse=False,
    )


def test_f4_github_issues_not_pulls():
    match = ChatActionMapper().match_segment(
        "search GitHub issues mentioning billing",
        connected_integrations=["github"],
    )
    assert match is not None
    assert "issues" in match.tool_name
    assert "pulls" not in match.tool_name


def test_f4_clickup_tasks_not_spaces():
    match = ChatActionMapper().match_segment(
        "list my open ClickUp tasks",
        connected_integrations=["clickup"],
    )
    assert match is not None
    assert "tasks" in match.tool_name
    assert "spaces" not in match.tool_name


def test_f4_salesforce_contacts_not_leads():
    match = ChatActionMapper().match_segment(
        "find Salesforce contacts named Sarah",
        connected_integrations=["salesforce"],
    )
    assert match is not None
    assert "contacts" in match.tool_name
    assert "leads" not in match.tool_name
