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
