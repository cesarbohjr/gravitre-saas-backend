"""Voice 3.0 Phase 5 — conversational polish unit tests.

Covers the three flag-gated pieces: Register 5b prompt content, per-turn spoken
length bands, and played-audio reconciliation after barge-in.
"""
from __future__ import annotations

from app.config import Settings
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
from app.services.pipecat_voice.voice_conversational_polish import (
    reconcile_played_audio,
    resolve_conversational_polish_flags,
    resolve_response_length_band,
    response_length_directive,
    spoken_prompt_v2_section,
)
from app.services.tier1_voice_service import voice_status


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


class TestSpokenPromptV2Section:
    def test_delivery_directives_present(self):
        section = spoken_prompt_v2_section()
        assert "Register 5b" in section
        assert "Write for the ear" in section
        assert "One idea per sentence" in section
        assert "Never speak punctuation" in section

    def test_interruption_directive_present(self):
        section = spoken_prompt_v2_section()
        assert "do not restart the sentence they cut off" in section

    def test_does_not_reintroduce_markdown(self):
        section = spoken_prompt_v2_section()
        assert "```" not in section


class TestResponseLengthBands:
    def test_very_short_utterance_is_terse(self):
        band = resolve_response_length_band("status?")
        assert band.band == "terse"
        assert band.max_sentences == 1

    def test_short_utterance_is_brief(self):
        band = resolve_response_length_band("did the hubspot sync finish")
        assert band.band == "brief"
        assert band.max_sentences == 2

    def test_medium_utterance_is_standard(self):
        text = " ".join(["word"] * 20)
        band = resolve_response_length_band(text)
        assert band.band == "standard"
        assert band.reason == "medium_user_utterance"

    def test_explanatory_short_question_gets_standard_room(self):
        band = resolve_response_length_band("why did it fail")
        assert band.band == "standard"
        assert band.reason == "explanatory_question"

    def test_long_utterance_is_expansive(self):
        text = " ".join(["word"] * 45)
        band = resolve_response_length_band(text)
        assert band.band == "expansive"
        assert band.reason == "long_user_utterance"

    def test_multi_part_question_is_expansive_even_when_short(self):
        band = resolve_response_length_band("is it synced and also who owns it")
        assert band.band == "expansive"
        assert band.reason == "multi_part_question"

    def test_empty_input_is_terse_not_crash(self):
        band = resolve_response_length_band(None)
        assert band.band == "terse"

    def test_directive_states_ceiling_and_forbids_padding(self):
        directive = response_length_directive(resolve_response_length_band("status?"))
        assert "at most" in directive
        assert "ceiling, not a quota" in directive
        assert "Never add filler" in directive


class TestPlayedAudioReconciliation:
    def test_spoken_prefix_truncates_and_reports_dropped_tail(self):
        result = reconcile_played_audio(
            spoken_text="The sync finished.",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is True
        assert result.match_strategy == "exact_prefix"
        assert result.dropped_chars == len("The sync finished. Three records were skipped.") - len(
            "The sync finished."
        )

    def test_nothing_spoken_yields_empty_reconciled_text(self):
        result = reconcile_played_audio(spoken_text="", full_draft_text="Never heard this.")
        assert result.reconciled_text == ""
        assert result.truncated is True
        assert result.match_strategy == "nothing_spoken"
        assert result.dropped_chars == len("Never heard this.")

    def test_full_match_is_not_truncated(self):
        result = reconcile_played_audio(spoken_text="All of it.", full_draft_text="All of it.")
        assert result.reconciled_text == "All of it."
        assert result.truncated is False
        assert result.match_strategy == "full_match"
        assert result.dropped_chars == 0

    def test_no_shared_words_falls_back_to_draft_without_inventing_boundary(self):
        result = reconcile_played_audio(
            spoken_text="totally different words",
            full_draft_text="The sync finished.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is False
        assert result.match_strategy == "no_overlap_fallback_draft"

    def test_empty_draft_is_safe(self):
        result = reconcile_played_audio(spoken_text="", full_draft_text="")
        assert result.reconciled_text == ""
        assert result.truncated is False
        assert result.match_strategy == "empty_draft"


class TestPlayedAudioReconciliationAlignmentDrift:
    """REGRESSION: a strict ``draft.startswith(spoken)`` check silently dropped
    nothing whenever the TTS-aligned text differed from the LLM draft by
    whitespace, capitalisation, or punctuation — which is the common case, not the
    edge case. Each of these would have reported success while truncating zero
    characters.
    """

    def test_extra_whitespace_in_aligned_text_still_truncates(self):
        result = reconcile_played_audio(
            spoken_text="The  sync   finished.",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is True
        assert result.match_strategy == "word_prefix"

    def test_newlines_in_aligned_text_still_truncates(self):
        result = reconcile_played_audio(
            spoken_text="The sync\nfinished.",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is True

    def test_missing_punctuation_in_aligned_text_still_truncates(self):
        result = reconcile_played_audio(
            spoken_text="The sync finished",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is True

    def test_case_difference_in_aligned_text_still_truncates(self):
        result = reconcile_played_audio(
            spoken_text="the sync finished.",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync finished."
        assert result.truncated is True

    def test_partial_divergence_cuts_at_last_confirmed_word(self):
        result = reconcile_played_audio(
            spoken_text="The sync wobbled sideways",
            full_draft_text="The sync finished. Three records were skipped.",
        )
        assert result.reconciled_text == "The sync"
        assert result.truncated is True
        assert result.match_strategy == "diverged_word_prefix"
        assert result.matched_words == 2

    def test_reconciled_text_never_exceeds_draft(self):
        result = reconcile_played_audio(
            spoken_text="The sync finished completely and totally",
            full_draft_text="The sync finished.",
        )
        assert len(result.reconciled_text) <= len("The sync finished.")

    def test_meta_exposes_strategy_for_live_traces(self):
        meta = reconcile_played_audio(
            spoken_text="The  sync   finished.",
            full_draft_text="The sync finished. Three records were skipped.",
        ).as_meta()
        assert meta["match_strategy"] == "word_prefix"
        assert meta["dropped_chars"] > 0
        assert meta["matched_words"] == 3

    def test_meta_carries_no_transcript_text(self):
        """The audit payload is counts + strategy only — no spoken content."""
        meta = reconcile_played_audio(
            spoken_text="The sync finished.",
            full_draft_text="The sync finished. Three records were skipped.",
        ).as_meta()
        assert not any(isinstance(v, str) and " " in v for v in meta.values())


class TestPolishFlagResolution:
    def test_all_off_by_default(self):
        flags = resolve_conversational_polish_flags(_settings())
        assert flags == {
            "spoken_prompt_v2": False,
            "response_length_adapt_v1": False,
            "played_audio_reconcile_v1": False,
        }

    def test_flags_read_from_settings(self):
        flags = resolve_conversational_polish_flags(
            _settings(
                voice_spoken_prompt_v2=True,
                voice_response_length_adapt_v1=True,
                voice_played_audio_reconcile_v1=True,
            )
        )
        assert all(flags.values())

    def test_missing_attributes_do_not_raise(self):
        flags = resolve_conversational_polish_flags(object())
        assert not any(flags.values())


class TestUnifiedPromptComposition:
    def test_register_5b_only_appears_when_requested(self):
        without = build_module_d_unified_system_prompt(spoken_mode=True, include_few_shots=False)
        assert "Register 5b" not in without
        with_v2 = build_module_d_unified_system_prompt(
            spoken_mode=True,
            include_few_shots=False,
            spoken_prompt_v2=True,
        )
        assert "Register 5b" in with_v2

    def test_register_5_still_present_when_v2_enabled(self):
        prompt = build_module_d_unified_system_prompt(
            spoken_mode=True,
            include_few_shots=False,
            spoken_prompt_v2=True,
        )
        assert "Register 5 — SPOKEN" in prompt
        assert "Register 5b" in prompt

    def test_length_band_appended_when_provided(self):
        prompt = build_module_d_unified_system_prompt(
            spoken_mode=True,
            include_few_shots=False,
            spoken_length_band=resolve_response_length_band("status?"),
        )
        assert "Spoken length target for THIS turn" in prompt
        assert "**terse**" in prompt

    def test_polish_sections_never_leak_into_text_turns(self):
        prompt = build_module_d_unified_system_prompt(
            spoken_mode=False,
            include_few_shots=False,
            spoken_prompt_v2=True,
            spoken_length_band=resolve_response_length_band("status?"),
        )
        assert "Register 5b" not in prompt
        assert "Spoken length target" not in prompt


class TestVoiceStatusPhase5Block:
    def test_block_present_and_off_by_default(self):
        status = voice_status(_settings())
        block = status["phase5_conversational_polish"]
        assert block["spoken_prompt_v2"] is False
        assert block["response_length_adapt_v1"] is False
        assert block["played_audio_reconcile_v1"] is False

    def test_block_reflects_enabled_flags(self):
        status = voice_status(_settings(voice_played_audio_reconcile_v1=True))
        assert status["phase5_conversational_polish"]["played_audio_reconcile_v1"] is True
