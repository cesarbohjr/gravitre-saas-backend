"""Regression for the production 2026-10-08 count/resend/continuation incident."""
from unittest.mock import MagicMock, patch

import pytest

from app.services.cognitive_execution_replanner import build_cross_source_analytics_plan
from app.services.intent_gateway import response_cache_eligible, response_cache_put, response_cache_get
from app.services.listing_f2_read_turn import resolve_listing_read_message, try_listing_f2_read_turn
from app.services.tool_types import NormalizedResult

PROMPT = "How many companies do I have in HubSpot?"


def test_unclassified_request_does_not_default_to_website_analytics():
    assert build_cross_source_analytics_plan(
        PROMPT, capability_id=None,
        connected_integrations=["hubspot", "google_analytics", "google_search_console"],
    ) is None


@pytest.mark.parametrize("prompt", [PROMPT, "Count my Salesforce leads", "Show current Xero invoices"])
def test_connected_business_reads_cannot_replay_a_cached_refusal(prompt):
    assert not response_cache_eligible(prompt)
    response_cache_put("org", "conversation", prompt, "I need to run that.")
    assert response_cache_get("org", "conversation", prompt) is None


def test_read_continuation_uses_nearest_request_and_preserves_approval_ownership():
    state = {"recent_user_messages": [PROMPT, PROMPT, "Ok do that", "Ok do that"]}
    assert resolve_listing_read_message("Ok do that", state) == PROMPT
    assert resolve_listing_read_message("Ok do that", {
        **state, "pending_task": {"status": "awaiting_confirm", "type": "connector_action"},
    }) == "Ok do that"
    assert resolve_listing_read_message("Ok do that", {
        "recent_user_messages": [PROMPT, "Check website traffic", "Ok do that"],
    }) == "Ok do that"


@pytest.mark.parametrize("total", [0, 1, 57])
def test_company_count_uses_provider_total_not_page_length(total):
    result = NormalizedResult(success=True, action="hubspot.companies.search",
                              connector_id="hubspot", data={"total": total, "results": [{"id": "one"}]})
    with patch("app.services.listing_f2_read_turn.invoke_sealed_f1_read",
               return_value=(result, MagicMock(ok=True), MagicMock(observation_id="observation"))) as invoke:
        turn = try_listing_f2_read_turn(message=PROMPT, org_id="org", client=object(),
            settings=MagicMock(), connected_integrations=["hubspot"], task_state={})
    assert turn["workflow_status"] == "completed"
    assert turn["provider_result_evidence"]["result_count"] == total
    assert f"has {total} " in turn["message"]
    assert invoke.call_args.kwargs["action_key"] == "hubspot.companies.search"
    assert invoke.call_args.kwargs["proposed_args"]["filter_groups"]


def test_partial_page_without_total_never_becomes_an_account_count():
    result = NormalizedResult(success=True, action="hubspot.companies.search",
                              connector_id="hubspot", data={"results": [{"id": "one"}], "paging": {"next": {"after": "2"}}})
    with patch("app.services.listing_f2_read_turn.invoke_sealed_f1_read",
               return_value=(result, MagicMock(ok=True), MagicMock(observation_id="observation"))):
        turn = try_listing_f2_read_turn(message=PROMPT, org_id="org", client=object(),
            settings=MagicMock(), connected_integrations=["hubspot"], task_state={})
    assert turn["workflow_status"] == "blocked"
    assert "has 1 company" not in turn["message"]


@pytest.mark.asyncio
async def test_canonical_continuation_runs_company_read_before_stale_analytics():
    from app.services.canonical_cognitive_resolution import try_compiled_operational_read_turn

    sentinel = {"execution_path": "listing_f2_read", "workflow_status": "completed"}
    with patch("app.services.listing_f2_read_turn.try_listing_f2_read_turn", return_value=sentinel) as listing:
        turn = await try_compiled_operational_read_turn(message="Ok do that", resolution=None,
            org_id="org", client=object(), settings=MagicMock(), connected_integrations=["hubspot"],
            task_state={"recent_user_messages": [PROMPT, "Ok do that"],
                        "compiled_task": {"capability_id": "analytics.traffic_overview"}})
    assert turn is sentinel
    assert listing.call_args.kwargs["message"] == PROMPT
