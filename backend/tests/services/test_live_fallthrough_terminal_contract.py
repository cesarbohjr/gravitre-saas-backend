"""ECO-012/DEC-003: distinguish delegation from a confirmed terminal stop.

Actual LIVE decision/marker/audit functions; model and audit I/O are isolated.
No provider, persisted outcome or deployed acceptance is certified here.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.unified_turn_fallthrough import LIVE_FALLTHROUGH_REASONS
from app.services.unified_turn_reasoning_service import (
    UnifiedTurnShadowResult, _mark_live_fallthrough,
    apply_unified_turn_live, emit_unified_turn_shadow_audit,
)


@pytest.mark.parametrize("reason", sorted(LIVE_FALLTHROUGH_REASONS) + [
    "outcome_timeout", "unhandled_kind_future_kind",
])
def test_every_delegation_reason_audits_no_live_completion(reason):
    result = UnifiedTurnShadowResult(
        outcome_kind="connector_tool_proposal", live_served=True,
        tool_name="hubspot_search_contacts", requires_write_approval=True,
    )
    assert _mark_live_fallthrough(result, reason) is result
    with patch("app.workflows.audit.write_audit_event") as audit:
        emit_unified_turn_shadow_audit(
            client=MagicMock(), org_id="org", actor_id="user",
            conversation_id="conversation", result=result,
        )
    assert audit.call_count == 1
    assert audit.call_args.args[3] == "unified_turn.live.fallthrough"
    payload = audit.call_args.args[6]
    assert payload["fallthrough_reason"] == reason
    assert payload["live_served"] is False
    assert payload["shadow_user_visible"] is False
    assert payload["shadow_executes_tools"] is False
    assert payload["classical_path_active"] is True
    assert payload["requires_write_approval"] is True
    assert "turn_terminal_state" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken_mode", [False, True])
async def test_confirmed_stop_returns_terminal_payload_without_delegation(spoken_mode):
    stopped = UnifiedTurnShadowResult(
        outcome_kind="skipped", fallthrough_reason="chat_stop", error="stopped",
        user_message="Do not publish this partial model response.",
    )
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    state = {"synthetic_state": "preserved"}
    with (
        patch("app.services.unified_turn_pending_live.resolve_unified_live_pending_reply", AsyncMock(return_value=None)),
        patch("app.services.unified_turn_reasoning_service.run_unified_turn_shadow", AsyncMock(return_value=stopped)),
        patch("app.workflows.audit.write_audit_event") as audit,
        patch("app.services.live_classical_handoff.stash_live_classical_handoff") as handoff,
    ):
        result = await apply_unified_turn_live(
            org_id="org", user_id="user", conversation_id="conversation",
            message="Explain conversion rates.", task_state=state,
            conversation_history=[], connected_integrations=[],
            client=MagicMock(), settings=settings, spoken_mode=spoken_mode,
        )
    assert result is not None and result["stop_pipeline"] is True
    assert result["turn_terminal_state"] == "cancelled"
    assert result["message"] == "" and result["tool_results"] == []
    assert result["model"] == "cancelled"
    assert result["task_state"] is state
    assert stopped.fallthrough_reason == "chat_stop"
    handoff.assert_not_called()
    assert audit.call_args.args[3] == "unified_turn.live.cancelled"
    assert audit.call_args.args[6]["classical_path_active"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,reason,error", [
    ("skipped", None, None),
    ("error", None, "provider unavailable"),
    ("skipped", "chat_stop", None),
    ("skipped", None, "stopped"),
])
async def test_other_skips_and_errors_retain_classical_delegation(kind, reason, error):
    outcome = UnifiedTurnShadowResult(outcome_kind=kind, fallthrough_reason=reason, error=error)
    settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
    with (
        patch("app.services.unified_turn_pending_live.resolve_unified_live_pending_reply", AsyncMock(return_value=None)),
        patch("app.services.unified_turn_reasoning_service.run_unified_turn_shadow", AsyncMock(return_value=outcome)),
        patch("app.workflows.audit.write_audit_event") as audit,
    ):
        result = await apply_unified_turn_live(
            org_id="org", user_id="user", conversation_id="conversation",
            message="Explain conversion rates.", task_state={},
            conversation_history=[], connected_integrations=[], client=MagicMock(),
            settings=settings,
        )
    assert result is None
    assert outcome.fallthrough_reason == f"outcome_{kind}"
    assert audit.call_args.args[3] == "unified_turn.live.fallthrough"
    assert audit.call_args.args[6]["classical_path_active"] is True
