"""Voice 3.0 spoken register acceptance contracts (provider-independent)."""

from app.services.pipecat_voice.voice_conversational_polish import spoken_prompt_v2_section


def test_spoken_registers_cover_requested_contexts():
    section = spoken_prompt_v2_section()
    for register in ("Professional:", "Casual:", "Social:", "Expressive:"):
        assert register in section


def test_spoken_registers_do_not_override_governance_or_invent_disfluency():
    section = spoken_prompt_v2_section()
    for requirement in (
        "approval requirements",
        "verified answer",
        "Never add \"uh\", \"um\"",
        "precision overrides playfulness",
    ):
        assert requirement in section
