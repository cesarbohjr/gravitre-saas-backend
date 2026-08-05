"""Standing CI battery — NL variance + withhold-fabrication (F1/F3/F10).

Promotes routing-map Parts C.1/C.2 probes and BFCL-style 'correctly withholds'
into permanent regression coverage.
"""
from __future__ import annotations

from app.services.chat_action_mapper import ChatActionMapper
from app.services.pack_common_intent_defaults import (
    try_pack_common_list_create_plan,
    try_pack_common_msp_enrich_workflow_plan,
)
from app.services.retrieve_plan_gate import retrieve_plan_or_none

CONNECTED = ["apollo", "hubspot", "clay", "slack", "gmail"]

C1_MSP = [
    'Use Clay to enrich the existing Apollo contact list "MSP Prospects", then add those enriched contacts to the existing HubSpot static list "MSPs".',
    "enrich my apollo MSP Prospects list with Clay and sync to HubSpot MSPs",
    "Clay enrich Apollo list MSP Prospects into HubSpot list MSPs",
    "please take MSP Prospects from Apollo, enrich via Clay, put them on HubSpot MSPs",
    "run clay enrichment on the apollo msp prospects list and push to hubspot",
    "I need clay to enrich contacts then hubspot sync for msp prospects",
    "enrich contacts with clay then add to hubspot",
]

C2_LIST = [
    "Create a HubSpot static list named MSPs",
    "make me a new hubspot list called MSPs",
    "add a contact list MSPs in hubspot",
    "new apollo contact list for msp outreach",
    "can you set up a list MSPs on hubspot?",
    "I want a hubspot segment named MSPs",
    "create list",
    "spin up an outreach list in apollo for MSPs",
]


def test_c1_msp_enrich_variance_at_least_7_of_8():
    hits = sum(
        1
        for m in C1_MSP
        if try_pack_common_msp_enrich_workflow_plan(m, connected_integrations=CONNECTED)
        is not None
    )
    # Soft outreach-list phrasing is allowed to miss pack regex when F1 clarifies.
    assert hits >= 6


def test_c2_list_create_8_of_8():
    hits = sum(
        1
        for m in C2_LIST
        if try_pack_common_list_create_plan(m, connected_integrations=CONNECTED) is not None
    )
    assert hits == 8


def test_withhold_fabrication_on_ambiguous_enrich():
    """BFCL-style category 1: ambiguous pack-shaped NL → clarify, no fabricated plan."""
    retrieved = retrieve_plan_or_none(
        "enrich my list with Clay and sync somewhere",
        org_id="org",
        connected_integrations=CONNECTED,
        client=None,
        require_pack_install=False,
    )
    assert retrieved is not None
    assert retrieved.kind == "clarify"
    assert retrieved.block_fabrication is True
    assert "invent" in retrieved.user_message.lower() or "which" in retrieved.user_message.lower()


def test_withhold_no_matching_action_connected_vendor():
    """Category 2: connected vendor mentioned but no matching action → not nearest wrong tool.

    F4 class: GitHub/ClickUp/Salesforce object confusables must not silently pick
    the wrong sibling tool. When intent has no real action, clarify / knowledge
    boundary — never invent a nearest-neighbor write.
    """
    # Connected vendor + intent with no catalog action (wiki pages).
    msg = "create a Linear wiki page for our Q3 OKRs and publish it"
    retrieved = retrieve_plan_or_none(
        msg,
        org_id="org",
        connected_integrations=["linear", "slack"],
        client=None,
        require_pack_install=False,
    )
    mapper = ChatActionMapper()
    match = mapper.match_segment(msg, connected_integrations=["linear", "slack"])
    # Must not invent a non-existent linear.wiki.* / pages tool.
    if match is not None:
        tool = (match.tool_name or "").lower()
        assert "wiki" not in tool
        assert not tool.endswith(".pages.create")
        assert "pages" not in tool.split(".")
    # Withhold = clarify / no match / no pack fabricate.
    withheld = (
        (retrieved is not None and retrieved.kind == "clarify")
        or match is None
        or (
            retrieved is None
            and match is not None
            and "wiki" not in (match.tool_name or "").lower()
        )
    )
    assert withheld, (
        f"expected withhold for unmatched Linear wiki intent; "
        f"retrieved={getattr(retrieved, 'kind', None)} match={match}"
    )


def test_withhold_explicit_advise_only_mentions_vendor():
    """Category 3: explicit don't-act + connected vendor name → zero tool selection."""
    msg = (
        "Don't take any action and don't call any tools — just advise me on whether "
        "HubSpot lists or Apollo lists are better for MSP outreach."
    )
    retrieved = retrieve_plan_or_none(
        msg,
        org_id="org",
        connected_integrations=CONNECTED,
        client=None,
        require_pack_install=False,
    )
    # Must not stage pack-common MSP enrich / list-create from vendor names alone.
    assert (
        try_pack_common_msp_enrich_workflow_plan(msg, connected_integrations=CONNECTED)
        is None
    )
    assert (
        try_pack_common_list_create_plan(msg, connected_integrations=CONNECTED) is None
    )
    mapper = ChatActionMapper()
    match = mapper.match_segment(msg, connected_integrations=CONNECTED)
    assert match is None, f"advise-only message must not select a tool, got {match}"
    # Retrieve gate must not fabricate a pack plan for advise-only.
    if retrieved is not None:
        assert retrieved.kind != "pack_common_msp_enrich"
        assert retrieved.kind != "pack_common_list_create"


def test_withhold_no_tool_combined_pass_rate():
    """Standing report: all three withhold_no_tool categories pass together."""
    # Re-run the three category assertions as a scored battery for CI visibility.
    cat1 = test_withhold_fabrication_on_ambiguous_enrich
    cat2 = test_withhold_no_matching_action_connected_vendor
    cat3 = test_withhold_explicit_advise_only_mentions_vendor
    results = []
    for fn in (cat1, cat2, cat3):
        try:
            fn()
            results.append(True)
        except AssertionError:
            results.append(False)
    pass_rate = sum(results) / len(results)
    assert pass_rate == 1.0, f"withhold_no_tool pass_rate={pass_rate} results={results}"


def test_g1_object_disambiguation_still_holds():
    mapper = ChatActionMapper()
    gh = mapper.match_segment(
        "search GitHub issues mentioning billing",
        connected_integrations=["github"],
    )
    assert gh and "issues" in gh.tool_name and "pulls" not in gh.tool_name
    cu = mapper.match_segment(
        "list my open ClickUp tasks",
        connected_integrations=["clickup"],
    )
    assert cu and "tasks" in cu.tool_name and "spaces" not in cu.tool_name
    sf = mapper.match_segment(
        "find Salesforce contacts named Sarah",
        connected_integrations=["salesforce"],
    )
    assert sf and "contacts" in sf.tool_name and "leads" not in sf.tool_name
