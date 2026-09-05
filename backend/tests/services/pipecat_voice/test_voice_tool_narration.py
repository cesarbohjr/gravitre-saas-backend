"""Unit tests for the Phase 2 (conversational-realism) narration helpers."""
from __future__ import annotations

from unittest.mock import patch

from app.services.pipecat_voice.voice_tool_narration import (
    is_write_shaped_tool_name,
    narrate_connector_write_executing,
    narrate_tool_completed,
    narrate_tool_started,
    will_execute_staged_connector_write,
)


class TestNarrateToolStarted:
    def test_known_friendly_tool_name_maps_to_hand_tuned_phrase(self) -> None:
        assert narrate_tool_started("getPipelineHealth") == "Let me check your pipeline."

    def test_unknown_camel_case_tool_falls_back_to_generic_humanizer(self) -> None:
        assert narrate_tool_started("checkInvoiceStatus") == "Let me check check invoice status."

    def test_unknown_snake_case_tool_falls_back_to_generic_humanizer(self) -> None:
        assert narrate_tool_started("check_invoice_status") == "Let me check check invoice status."

    def test_empty_tool_name_still_returns_a_safe_generic_phrase(self) -> None:
        assert narrate_tool_started("") == "Let me check that."


class TestNarrateToolCompleted:
    def test_non_dict_output_is_never_narrated(self) -> None:
        assert narrate_tool_completed("anyTool", "raw string") is None
        assert narrate_tool_completed("anyTool", None) is None
        assert narrate_tool_completed("anyTool", [1, 2, 3]) is None

    def test_list_result_key_produces_a_real_count(self) -> None:
        assert narrate_tool_completed("listOpportunities", {"results": [1, 2, 3]}) == "Found 3."

    def test_count_key_produces_a_real_count(self) -> None:
        assert narrate_tool_completed("x", {"totalResults": 7}) == "Found 7."

    def test_zero_results_is_silence_not_a_fake_finding(self) -> None:
        assert narrate_tool_completed("x", {"results": []}) is None
        assert narrate_tool_completed("x", {"totalResults": 0}) is None

    def test_explicit_failure_flag_produces_honest_error_narration(self) -> None:
        out = narrate_tool_completed("updateDeal", {"success": False, "error": "vendor rejected it"})
        assert out == "That didn't go through — vendor rejected it."

    def test_error_key_alone_without_explicit_success_flag_still_narrates_failure(self) -> None:
        out = narrate_tool_completed("updateDeal", {"error": "timeout"})
        assert out == "That didn't go through — timeout."

    def test_failure_with_no_message_falls_back_to_tool_name(self) -> None:
        out = narrate_tool_completed("getConnectorStatus", {"success": False})
        assert out == "That didn't go through when checking your connections."

    def test_opaque_shape_with_no_recognizable_key_stays_silent(self) -> None:
        """MUTATION PROOF: this must return None, never an invented sentence —
        a shape narrate_tool_completed doesn't understand must never be
        spoken as if it were a real finding.
        """
        assert narrate_tool_completed("getConnectorStatus", {"status": "connected"}) is None


class TestIsWriteShapedToolName:
    def test_known_write_verbs_are_detected(self) -> None:
        for name in (
            "updateDealStage",
            "createContact",
            "sendEmail",
            "deleteRecord",
            "moveDealStage",
            "cancelMeeting",
        ):
            assert is_write_shaped_tool_name(name) is True, name

    def test_read_shaped_names_are_not_flagged_as_writes(self) -> None:
        for name in ("getPipelineHealth", "listOpportunities", "searchKnowledgeBase"):
            assert is_write_shaped_tool_name(name) is False, name


class TestPhase3ExecutingSpeech:
    def test_write_shaped_tool_start_speaks_executing_not_checking(self) -> None:
        """MUTATION PROOF: a write tool must say 'I'm updating that now' —
        not the read-shaped 'Let me check' phrasing, which would misstate
        real in-progress execution as a mere lookup.
        """
        assert narrate_tool_started("updateDealStage") == "I'm updating that now."

    def test_read_shaped_tool_start_still_uses_checking_phrasing(self) -> None:
        assert narrate_tool_started("getPipelineHealth") == "Let me check your pipeline."


class TestPhase3ConfirmedSpeech:
    def test_write_success_with_real_stage_field_is_narrated_honestly(self) -> None:
        out = narrate_tool_completed("moveDealStage", {"success": True, "stage": "Negotiation"})
        assert out == "Done — I moved it to Negotiation."

    def test_write_success_with_no_specific_field_gets_generic_honest_confirmation(self) -> None:
        """MUTATION PROOF: with no real field to read back, the sentence must
        stay generic ('Done, that went through') rather than inventing a
        specific-sounding detail ('Done, I moved Acme to Negotiation') that
        was never actually in the tool's own output.
        """
        out = narrate_tool_completed("updateDealStage", {"success": True})
        assert out == "Done, that went through."

    def test_write_success_is_never_claimed_before_a_real_returned_observation(self) -> None:
        """MUTATION PROOF (HARD CONSTRAINT): success=True is required in the
        REAL output dict — there is no code path in this function that can
        produce a CONFIRMED sentence from anything else (no default-True,
        no inference from tool name alone).
        """
        assert narrate_tool_completed("updateDealStage", {}) is None
        assert narrate_tool_completed("updateDealStage", {"success": None}) is None


def _staged_confirm_state(**overrides: object) -> dict:
    pending: dict = {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "params": {"label": "Create contact list Q3 Leads"},
    }
    pending.update(overrides)
    return {"pending_task": pending}


class TestWillExecuteStagedConnectorWrite:
    def test_confirm_message_on_staged_awaiting_confirm_write_is_true(self) -> None:
        assert will_execute_staged_connector_write(_staged_confirm_state(), "yes") is True

    def test_alternate_confirm_phrasing_is_also_true(self) -> None:
        for msg in ("confirm", "go ahead", "do it", "sounds good", "run", "execute"):
            assert will_execute_staged_connector_write(_staged_confirm_state(), msg) is True, msg

    def test_no_task_state_is_false(self) -> None:
        assert will_execute_staged_connector_write(None, "yes") is False

    def test_no_pending_task_is_false(self) -> None:
        assert will_execute_staged_connector_write({}, "yes") is False

    def test_non_connector_action_pending_type_is_false(self) -> None:
        """MUTATION PROOF: a strategic-plan or orchestration pending_task must
        never trigger connector-write EXECUTING speech — different shape,
        different (unmodeled) execution semantics.
        """
        state = _staged_confirm_state(type="connector_orchestration")
        assert will_execute_staged_connector_write(state, "yes") is False

    def test_awaiting_admin_approval_status_is_false(self) -> None:
        """MUTATION PROOF (HARD CONSTRAINT): the user cannot approve this
        themselves — confirming it only sends it for admin approval, it
        never reaches execute_plan() on this turn.
        """
        state = _staged_confirm_state(status="awaiting_admin_approval")
        assert will_execute_staged_connector_write(state, "yes") is False

    def test_awaiting_params_status_is_false(self) -> None:
        state = _staged_confirm_state(status="awaiting_params")
        assert will_execute_staged_connector_write(state, "yes") is False

    def test_non_confirm_message_is_false(self) -> None:
        assert (
            will_execute_staged_connector_write(_staged_confirm_state(), "what's the subject line?")
            is False
        )

    def test_empty_message_is_false(self) -> None:
        assert will_execute_staged_connector_write(_staged_confirm_state(), "") is False

    def test_active_hold_prompt_is_false(self) -> None:
        """MUTATION PROOF: a hold-prompt turn resolves to abandon/proceed
        logic in conversation_turn_controller.py, not a direct execute — a
        bare 'yes' there is not the same confirmation this gate models.
        """
        state = _staged_confirm_state()
        state["pending_hold_prompt"] = True
        assert will_execute_staged_connector_write(state, "yes") is False

    def test_fast_classifier_disagreement_overrides_the_raw_regex_match(self) -> None:
        """MUTATION PROOF: even though CONFIRM_PATTERN matches, if the real
        deterministic classifier used by the connector turn controller
        explicitly disagrees (reject/modify/clarify/etc.), this must stay
        False rather than trust the regex alone.
        """
        with patch(
            "app.services.pending_reply_classifier.classify_pending_reply_fast",
            return_value="modify",
        ):
            assert will_execute_staged_connector_write(_staged_confirm_state(), "confirm") is False

    def test_fast_classifier_returning_none_still_allows_true(self) -> None:
        """The real classifier returns None when it can't decide deterministically
        (falls through to an async LLM call elsewhere) — that must not block
        a message that otherwise clearly matches the confirm gate.
        """
        with patch(
            "app.services.pending_reply_classifier.classify_pending_reply_fast",
            return_value=None,
        ):
            assert will_execute_staged_connector_write(_staged_confirm_state(), "yes") is True


class TestNarrateConnectorWriteExecuting:
    def test_known_write_verb_label_produces_a_matching_gerund(self) -> None:
        assert (
            narrate_connector_write_executing("Create contact list Q3 Leads")
            == "One moment, I'm creating that now."
        )

    def test_send_verb_label(self) -> None:
        assert (
            narrate_connector_write_executing("Send email to Sarah")
            == "One moment, I'm sending that now."
        )

    def test_no_label_falls_back_to_generic_honest_phrase(self) -> None:
        assert narrate_connector_write_executing(None) == "One moment, I'm doing that now."
        assert narrate_connector_write_executing("") == "One moment, I'm doing that now."

    def test_label_with_no_recognizable_verb_falls_back_to_generic_phrase(self) -> None:
        """MUTATION PROOF: a label that doesn't start with a known write verb
        must never produce the broken 'I'm that now.' — is_write_shaped_tool_name
        must gate the gerund phrase, not _gerund_phrase's own bare fallback.
        """
        out = narrate_connector_write_executing("Zendesk Ticket Escalation")
        assert out == "One moment, I'm doing that now."
        assert "I'm that now" not in out
