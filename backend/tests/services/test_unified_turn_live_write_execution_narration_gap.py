"""Mutation-proof regression tests locking the STA follow-up finding:

``unified_turn_reasoning_service.py`` (Phase 4 "unified turn LIVE") never
itself executes a real connector write. Every write-shaped ``stop_pipeline``
resolution either (a) stages an approval ask (``awaiting_confirm`` /
``awaiting_plan_confirm``) or (b) defers entirely to classical
(``return None``) — which is where a real write eventually executes, via
``run_connector_turn`` (already covered by
``voice_tool_narration.will_execute_staged_connector_write`` /
``narrate_connector_write_executing``, wired in
``app/operators/agent_intelligence.py``) or classical ReAct tool_start/
tool_complete events (already covered by ``narrate_tool_started`` /
``narrate_tool_completed`` via ``cognitive_llm.py``).

Because no genuine "a real write just executed / is about to execute inside
this file" code path exists, no new EXECUTING narration hook was added here
(per the same false-positive-proof discipline documented in
``will_execute_staged_connector_write``'s own docstring: a false positive —
narrating "doing X" on a turn that only staged an approval ask or deferred —
is strictly worse than adding nothing). These tests exist to keep that
finding true over time: if a future change makes this file actually execute
a write, or makes ``spoken_mode`` leak execution-claiming text into a
staging/clarify payload, one of the tests below must fail.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.chat_orchestration_service import OrchestrationStep
from app.services.unified_turn_reasoning_service import (
    UnifiedTurnShadowResult,
    apply_unified_turn_live,
)

# Execution-claiming past-tense language that must never appear in a payload
# this file produces for a write-shaped turn that has NOT actually executed
# anything (staging / approval-ask / clarify payloads only).
_EXECUTION_CLAIM_MARKERS = (
    "done,",
    "done —",
    "i've sent",
    "i sent",
    "i've created",
    "i created",
    "sent it",
    "went through",
    "all set",
)


def _assert_no_execution_claim(message: str) -> None:
    lower = (message or "").lower()
    for marker in _EXECUTION_CLAIM_MARKERS:
        assert marker not in lower, f"unexpected execution claim {marker!r} in: {message!r}"


class TestWriteApprovalStagingNeverClaimsExecution:
    """The ``plan.requires_approval`` branch (~line 2433 onward) stages
    ``awaiting_confirm`` — it must never itself claim a write went through,
    and ``spoken_mode`` must not change that payload at all (false-positive
    proof: no voice-only narration was smuggled into this branch).
    """

    @staticmethod
    def _proposal() -> UnifiedTurnShadowResult:
        return UnifiedTurnShadowResult(
            outcome_kind="connector_tool_proposal",
            tool_name="gmail_messages_send",
            tool_invoke_action="gmail.messages.send",
            tool_arguments={
                "to": "demo@example.com",
                "subject": "Hi",
                "body": "Test body",
            },
            requires_write_approval=True,
            connected_integrations=["gmail"],
            model="test",
        )

    async def _run(self, *, spoken_mode: bool) -> dict:
        settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
        plan = ConnectorActionPlan(
            tool_name="gmail_messages_send",
            invoke_action="gmail.messages.send",
            integration="gmail",
            kind="write",
            label="Send email",
            args={
                "to": "demo@example.com",
                "subject": "Hi",
                "body": "Test body",
            },
            requires_approval=True,
        )
        state = MagicMock()
        state.update_task_state = AsyncMock()
        state.get_task_state = AsyncMock(
            return_value={
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": {"invoke_action": "gmail.messages.send"},
                }
            }
        )
        with (
            patch(
                "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
                new=AsyncMock(return_value=self._proposal()),
            ),
            patch("app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit"),
            patch("app.services.react_write_gate.plan_from_react_tool_call", return_value=plan),
            patch("app.services.tool_registry.get_tool_registry", return_value=MagicMock()),
            patch(
                "app.services.conversation_state_service.get_conversation_state_service",
                return_value=state,
            ),
            patch(
                "app.services.connector_parameter_inference.infer_missing_parameters",
                side_effect=lambda p, _ctx: p,
            ),
            # Force the full write-approval staging branch (no missing params).
            patch(
                "app.services.connector_action_workflows.missing_params_stage_patch",
                return_value=None,
            ),
        ):
            out = await apply_unified_turn_live(
                org_id="org",
                user_id="user",
                conversation_id="conv",
                message='Send email to demo@example.com with subject "Hi" and body "Test body"',
                task_state={},
                conversation_history=[],
                connected_integrations=["gmail"],
                settings=settings,
                spoken_mode=spoken_mode,
            )
        assert out is not None
        return out

    @pytest.mark.asyncio
    async def test_stages_awaiting_confirm_not_executed(self) -> None:
        out = await self._run(spoken_mode=False)
        assert out["stop_pipeline"] is True
        assert out["dialogue_mode"] == "confirm"
        assert out["pending_task"]["status"] == "awaiting_confirm"
        _assert_no_execution_claim(out["message"])

    @pytest.mark.asyncio
    async def test_spoken_mode_true_produces_identical_payload_shape(self) -> None:
        """MUTATION PROOF: spoken_mode must not alter this staging payload at
        all — there is no EXECUTING narration hook in this branch, so a
        voice turn and a text turn must resolve identically here.
        """
        text_out = await self._run(spoken_mode=False)
        voice_out = await self._run(spoken_mode=True)
        assert voice_out["dialogue_mode"] == text_out["dialogue_mode"] == "confirm"
        assert (
            voice_out["pending_task"]["status"]
            == text_out["pending_task"]["status"]
            == "awaiting_confirm"
        )
        assert voice_out["message"] == text_out["message"]
        _assert_no_execution_claim(voice_out["message"])


class TestBareConfirmOfStagedWriteNeverResolvesInsideLive:
    """If a write was already staged (by this file, by ``retrieve_plan_gate``,
    or by classical) as ``pending_task={"type": "connector_action",
    "status": "awaiting_confirm"}``, a bare "yes" must NEVER be resolved
    inside ``apply_unified_turn_live`` itself — ``has_pending_family`` must
    kick this out to ``return None`` so classical / ``run_connector_turn``
    (which already has EXECUTING narration coverage) handles the real
    execution. This is *why* no new narration hook belongs in this file.
    """

    @pytest.mark.asyncio
    async def test_confirm_of_staged_connector_action_returns_none(self) -> None:
        settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
        task_state = {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    "invoke_action": "gmail.messages.send",
                    "label": "Send email",
                },
            }
        }
        with (
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
            ) as shadow_mock,
        ):
            out = await apply_unified_turn_live(
                org_id="org",
                user_id="user",
                conversation_id="conv",
                message="yes",
                task_state=task_state,
                conversation_history=[],
                connected_integrations=["gmail"],
                settings=settings,
                spoken_mode=True,
            )
        assert out is None
        # The real-write single-model-call path must never even run for a bare
        # confirm of an already-staged write — has_pending_family exits first.
        shadow_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_of_staged_orchestration_plan_returns_none(self) -> None:
        """Same guarantee for a staged multi-step ``connector_orchestration``
        plan — a bare "yes" resuming it is never resolved by this file
        either (it defers to ``ChatOrchestrationService`` in the classical
        continuation of ``agent_intelligence.py``, a separate call site).
        """
        settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
        task_state = {
            "pending_task": {
                "type": "connector_orchestration",
                "status": "awaiting_plan_confirm",
                "params": {"goal": "multi-step task", "steps": []},
            }
        }
        with (
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
            ) as shadow_mock,
        ):
            out = await apply_unified_turn_live(
                org_id="org",
                user_id="user",
                conversation_id="conv",
                message="yes",
                task_state=task_state,
                conversation_history=[],
                connected_integrations=["hubspot", "slack"],
                settings=settings,
                spoken_mode=True,
            )
        assert out is None
        shadow_mock.assert_not_called()


class TestOrchestrationBeforeDeferStagesOnlyNeverExecutes:
    """The "stage the plan on LIVE before bare classical defer" branch
    (~line 2119 onward) calls into ``ChatOrchestrationService.process_turn``
    directly. Lock that, from this call site, it can only ever reach the
    plan-staging branch (``_present_plan_confirm``) — never the real
    execution branches (``_start_execution`` / ``_execute_current_step``).
    """

    HS_SLACK_TRY = (
        "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
    )

    @pytest.mark.asyncio
    async def test_never_reaches_real_execution_methods(self) -> None:
        shadow = UnifiedTurnShadowResult(
            outcome_kind="conversational_reply",
            user_message="I can help with that.",
            connected_integrations=["hubspot", "slack"],
            model="test",
        )
        steps = [
            OrchestrationStep(
                step_id="step_1",
                segment="Search HubSpot for high-intent leads",
                label="Search contacts",
                kind="read",
                supported=True,
                requires_approval=False,
                plan=ConnectorActionPlan(
                    tool_name="hubspot_contacts_search",
                    invoke_action="hubspot.contacts.search",
                    integration="hubspot",
                    kind="read",
                    label="Search contacts",
                    args={"query": "high-intent"},
                ),
            ),
            OrchestrationStep(
                step_id="step_2",
                segment="draft a follow-up in Slack for approval",
                label="Post message",
                kind="write",
                supported=True,
                requires_approval=True,
                plan=ConnectorActionPlan(
                    tool_name="slack_post_message",
                    invoke_action="slack.post_message",
                    integration="slack",
                    kind="write",
                    label="Post message",
                    args={"text": "follow-up"},
                    destructive=True,
                    requires_approval=True,
                ),
            ),
        ]
        refreshed = {
            "pending_task": {
                "type": "connector_orchestration",
                "status": "awaiting_plan_confirm",
                "params": {"goal": self.HS_SLACK_TRY, "steps": [s.to_dict() for s in steps]},
            }
        }
        state = MagicMock()
        state.update_task_state = AsyncMock()
        state.get_task_state = AsyncMock(
            side_effect=[
                {"pending_task": None, "clarified_params": {}},
                refreshed,
                refreshed,
            ]
        )
        settings = MagicMock()
        settings.unified_turn_live_enabled = True

        with (
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.pending_reply_classifier.has_pending_family",
                return_value=False,
            ),
            patch(
                "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
                new=AsyncMock(return_value=shadow),
            ),
            patch("app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit"),
            patch(
                "app.services.conversation_state_service.get_conversation_state_service",
                return_value=state,
            ),
            patch(
                "app.services.chat_orchestration_service.get_conversation_state_service",
                return_value=state,
            ),
            patch(
                "app.services.chat_orchestration_service.ChatOrchestrationService._build_plan",
                new=AsyncMock(return_value=steps),
            ),
            patch(
                "app.services.chat_orchestration_service.ChatOrchestrationService._start_execution",
            ) as start_exec_mock,
            patch(
                "app.services.chat_orchestration_service.ChatOrchestrationService._execute_current_step",
            ) as exec_step_mock,
        ):
            out = await apply_unified_turn_live(
                org_id="org-1",
                user_id="user-1",
                conversation_id="conv-try-hs-slack",
                message=self.HS_SLACK_TRY,
                task_state={},
                conversation_history=[],
                connected_integrations=["hubspot", "slack"],
                client=MagicMock(),
                settings=settings,
                spoken_mode=True,
            )

        assert out is not None
        assert out["stop_pipeline"] is True
        assert out["dialogue_mode"] == "confirm"
        assert out["pending_task"]["status"] == "awaiting_plan_confirm"
        _assert_no_execution_claim(out["message"])
        # MUTATION PROOF: the real execution methods on the delegated
        # orchestration service must never be invoked from this call site.
        start_exec_mock.assert_not_called()
        exec_step_mock.assert_not_called()


class TestSpokenModeSignalReachesThisService:
    """Proves the voice/spoken signal genuinely reaches
    ``apply_unified_turn_live`` (it is threaded into the single-model-call
    ``run_unified_turn_shadow``, which uses it only to select the SPOKEN
    system-prompt register) — while confirming it never becomes an
    EXECUTING-narration trigger anywhere in this file.
    """

    async def _call_with(self, spoken_mode: bool) -> None:
        settings = MagicMock(unified_turn_live_enabled=True, openai_api_key="sk-test")
        shadow = UnifiedTurnShadowResult(
            outcome_kind="conversational_reply",
            user_message="Sure, here's the status.",
            model="test",
        )
        with (
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_channel_override_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_meta_capability_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_pending_live.resolve_unified_live_pending_reply",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.unified_turn_reasoning_service.run_unified_turn_shadow",
                new=AsyncMock(return_value=shadow),
            ) as shadow_mock,
            patch("app.services.unified_turn_reasoning_service.emit_unified_turn_shadow_audit"),
        ):
            await apply_unified_turn_live(
                org_id="org",
                user_id="user",
                conversation_id="conv",
                message="What's the pipeline status?",
                task_state={},
                conversation_history=[],
                connected_integrations=[],
                settings=settings,
                spoken_mode=spoken_mode,
            )
        return shadow_mock

    @pytest.mark.asyncio
    async def test_spoken_mode_true_is_forwarded_to_run_unified_turn_shadow(self) -> None:
        shadow_mock = await self._call_with(True)
        assert shadow_mock.await_args.kwargs["spoken_mode"] is True

    @pytest.mark.asyncio
    async def test_spoken_mode_false_is_forwarded_to_run_unified_turn_shadow(self) -> None:
        shadow_mock = await self._call_with(False)
        assert shadow_mock.await_args.kwargs["spoken_mode"] is False
