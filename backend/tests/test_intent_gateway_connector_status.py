"""Intent gateway shortcut for connector status questions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway


@pytest.mark.asyncio
@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
async def test_gateway_shortcuts_is_clay_connected(mock_rows):
    mock_rows.return_value = (
        [
            {
                "vendor": "hubspot",
                "execution_available": True,
                "auth_status": "connected",
                "display_status": "connected",
                "connected": True,
            }
        ],
        False,
    )
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message="Is Clay connected?",
            org_id="org-1",
            client=MagicMock(),
            connected_integrations=["hubspot"],
            settings=MagicMock(),
        )
    )
    assert decision.action == "shortcut"
    assert decision.candidate_id == "connector_status"
    assert decision.answer is not None
    assert "Clay isn't connected" in decision.answer
    assert "assistant_" not in decision.answer


# Confirmed live incident, retrieval A, 2026-09-21T15:25:18Z, org f07e57c0…
# text_head named four routing slugs as connected with tool_names: [].
RETRIEVAL_AB_A_LIVE_MESSAGE = "What connectors are connected? (retrieval-ab A 202609211525)"
RETRIEVAL_AB_A_LIVE_SLUGS = ["apollo", "google_ads", "google_search_console", "hubspot"]
RETRIEVAL_AB_A_LIVE_FALSE_CLAIM = (
    "You have Apollo, Google Ads, Google Search Console, and Hubspot connected."
)


@pytest.mark.asyncio
@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
async def test_retrieval_ab_a_20260921_live_false_claim_blocked_without_getconnectorstatus(
    mock_rows,
):
    """Named regression for Milestone 1 retrieval_ab A on 720a0650.

    The model stated unverified connector state as fact from the routing slug
    snapshot. Gateway must shortcut, call getConnectorStatus, and must not
    emit that sentence when the live check fails.
    """
    from app.services.operator_task_intent import is_operator_task_shaped

    mock_rows.return_value = (None, True)
    assert is_operator_task_shaped(RETRIEVAL_AB_A_LIVE_MESSAGE) is False
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message=RETRIEVAL_AB_A_LIVE_MESSAGE,
            org_id="f07e57c0-1501-4000-8000-c04e57a00001",
            client=MagicMock(),
            connected_integrations=RETRIEVAL_AB_A_LIVE_SLUGS,
            settings=MagicMock(),
        )
    )
    assert decision.action == "shortcut"
    assert decision.candidate_id == "connector_status"
    assert decision.reason != "operator_task_shaped"
    assert mock_rows.called
    assert decision.answer is not None
    assert decision.answer != RETRIEVAL_AB_A_LIVE_FALSE_CLAIM
    assert "Apollo" not in decision.answer
    assert "Google Ads" not in decision.answer
    assert "Google Search Console" not in decision.answer
    assert "Hubspot" not in decision.answer
    assert "couldn't verify" in decision.answer
    assert decision.extras.get("status_tool_invoked") is True
    assert decision.extras.get("verified_tool") is None


@pytest.mark.asyncio
@patch("app.services.connector_status_reply_service._rows_from_get_connector_status")
async def test_gateway_shortcuts_is_apollo_connected_despite_operator_work_regex(mock_rows):
    mock_rows.return_value = (
        [
            {
                "vendor": "apollo",
                "execution_available": True,
                "auth_status": "connected",
                "display_status": "connected",
                "connected": True,
            }
        ],
        False,
    )
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message="Is Apollo connected?",
            org_id="org-1",
            client=MagicMock(),
            connected_integrations=["apollo"],
            settings=MagicMock(),
        )
    )
    assert decision.action == "shortcut"
    assert decision.candidate_id == "connector_status"
    assert decision.reason != "operator_task_shaped"
    assert decision.answer is not None
    assert "connected" in decision.answer.lower()
    assert "checking" not in decision.answer.lower()
    assert "knowledge base" not in decision.answer.lower()

