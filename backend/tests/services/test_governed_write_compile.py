from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.governed_write_compile import try_governed_write_compile_turn


@pytest.mark.asyncio
async def test_send_email_disconnected_does_not_send() -> None:
    turn = await try_governed_write_compile_turn(
        message="Send an email.",
        org_id="org-1",
        client=object(),
        settings=None,
        connected_integrations=["hubspot"],
        task_state={},
    )
    assert turn is not None
    assert turn["workflow_status"] == "connector_not_connected"
    assert "sent" not in str(turn["message"]).lower() or "nothing" in str(turn["message"]).lower()
    assert "connect" in str(turn["message"]).lower()


@pytest.mark.asyncio
async def test_a_connected_send_goes_to_the_shared_draft_path() -> None:
    """A connected send is staged by the shared draft path (pending task,
    parameter ledger, one approval prompt), so its details survive the next
    turn. This compile step no longer answers it."""
    with patch("app.services.governed_write_compile.preflight_write_action") as mock_pf:
        turn = await try_governed_write_compile_turn(
            message="Send an email.",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["gmail"],
            task_state={},
        )
    assert turn is None
    mock_pf.assert_not_called()
