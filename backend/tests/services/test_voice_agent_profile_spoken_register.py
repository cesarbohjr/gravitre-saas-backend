"""Phase 4 (conversational-realism): SPOKEN register content contract.

Confirms Gravitre's existing Module D SPOKEN register (Register 5) enforces
the speech-native output policy the prompt spec calls for, extending the
existing section rather than building a second formatting system. These are
prompt-content contract tests: they assert the literal directives an editor
could accidentally delete or weaken are still present.
"""
from __future__ import annotations

from app.services.voice_agent_profile import spoken_register_section


class TestSpokenRegisterCoreDirectives:
    def test_default_length_cap_is_stated(self):
        section = spoken_register_section()
        assert "1–3 short sentences" in section or "1-3 short sentences" in section

    def test_most_important_information_first_is_stated(self):
        section = spoken_register_section()
        assert "most important fact or answer, first sentence" in section

    def test_no_restating_the_question_is_stated(self):
        section = spoken_register_section()
        assert "Never restate or paraphrase the user's question" in section

    def test_no_filler_preamble_is_stated_with_concrete_examples(self):
        section = spoken_register_section()
        assert "No unnecessary filler or preamble" in section
        assert "Certainly!" in section
        assert "Great question!" in section

    def test_mutation_proof_all_four_new_directives_present_together(self):
        """MUTATION PROOF: if any one of the four Phase 4 directives were
        deleted during an edit, this fails - each is checked independently
        so a partial revert is caught.
        """
        section = spoken_register_section()
        required_fragments = [
            "1–3 short sentences" if "1–3 short sentences" in section else "1-3 short sentences",
            "most important fact or answer, first sentence",
            "Never restate or paraphrase the user's question",
            "No unnecessary filler or preamble",
        ]
        for fragment in required_fragments:
            assert fragment in section, f"missing required SPOKEN register directive: {fragment!r}"


class TestSpokenRegisterPreexistingDirectivesUnchanged:
    """These directives already shipped before Phase 4 - confirm the Phase 4
    extension did not accidentally remove them (extend, don't replace).
    """

    def test_no_markdown_formatting_directive_present(self):
        section = spoken_register_section()
        assert "markdown headers" in section
        assert "bullet lists" in section
        assert "numbered lists" in section

    def test_spoken_transitions_directive_present(self):
        section = spoken_register_section()
        assert "first… then… finally…" in section

    def test_write_approval_speech_pattern_present(self):
        section = spoken_register_section()
        assert "Reply yes to confirm, or cancel to drop it." in section
