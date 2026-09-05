"""Unit tests for the Phase 2 (conversational-realism) narration helpers."""
from __future__ import annotations

from app.services.pipecat_voice.voice_tool_narration import (
    is_write_shaped_tool_name,
    narrate_tool_completed,
    narrate_tool_started,
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
