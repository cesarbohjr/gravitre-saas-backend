"""Spoken register + voice minutes plan rates."""
from __future__ import annotations

from app.billing.voice_minutes_plan_rates import (
    cogs_report,
    included_voice_minutes_for_plan,
    overage_usd_per_voice_minute,
)
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
from app.services.voice_acoustic_signal import extract_acoustic_features
from app.services.voice_agent_profile import agent_self_recognition_section
from app.services.voice_session_service import normalize_spoken_text, split_speakable_chunks


def test_spoken_register_in_prompt_when_spoken_mode():
    text = build_module_d_unified_system_prompt(spoken_mode=True)
    assert "Register 5 — SPOKEN" in text
    assert "bullet lists" in text.lower() or "numbered lists" in text.lower()


def test_self_recognition_injects_name():
    section = agent_self_recognition_section({"name": "Atlas"})
    assert "Atlas" in section
    assert "what's your name" in section.lower() or "assigned name" in section.lower()


def test_cogs_report_flags_real_math():
    report = cogs_report()
    assert report["blended_duplex_cogs_usd_per_min"] == 0.02645
    assert report["proposed_overage_usd_per_min"] == 0.12
    assert report["flag_for_review"] is True
    assert included_voice_minutes_for_plan(None, plan_code="node") == 60
    assert included_voice_minutes_for_plan(None, plan_code="command") == 1200
    assert overage_usd_per_voice_minute(None) == 0.12


def test_split_speakable_chunks_sentence_boundary():
    ready, rem = split_speakable_chunks("Hello there. More coming")
    assert ready == ["Hello there."]
    assert rem == "More coming"


def test_split_speakable_chunks_terminal_punct_no_trailing_space():
    """Short voice answers like 'Four.' must speak without waiting for whitespace."""
    ready, rem = split_speakable_chunks("Four.")
    assert ready == ["Four."]
    assert rem == ""


def test_split_speakable_chunks_earlier_clause_flush():
    """Spoken TTFA cut: flush a long clause before the old 80-char bar."""
    buf = "Gravitre helps teams automate connected workflows across systems and agents"
    ready, rem = split_speakable_chunks(buf, min_chars=12)
    assert ready, "expected an earlier clause flush"
    assert len(ready[0]) >= 12


def test_split_speakable_chunks_short_answer_mid_sentence_flush():
    """Short answers must not wait for '.' — flush once a first clause exists."""
    ready, rem = split_speakable_chunks("Two plus two equals", min_chars=12)
    assert ready, "expected mid-sentence flush before terminal punctuation"
    assert ready[0].startswith("Two")
    assert len(ready[0]) >= 12
    assert rem  # remainder kept for the next delta


def test_spoken_conversational_prompt_omits_few_shots():
    full = build_module_d_unified_system_prompt(spoken_mode=True, include_few_shots=True)
    lean = build_module_d_unified_system_prompt(spoken_mode=True, include_few_shots=False)
    assert "Few-shot demonstrations" in full
    assert "Few-shot demonstrations" not in lean
    assert "Register 5 — SPOKEN" in lean
    assert len(lean) < len(full)


def test_normalize_spoken_text_removes_visual_markdown():
    source = (
        "## Update\n"
        "- First point\n"
        "- second point\n"
        "Reply **yes** to continue.\n"
        "[Open run](https://example.com/run/123)\n"
    )
    spoken = normalize_spoken_text(source)
    assert spoken == "Update. First point. second point. Reply yes to continue. Open run."


def test_reconstitute_spoken_email_digit_words():
    from app.services.voice_session_service import reconstitute_spoken_identity_fields

    source = (
        "Create a HubSpot contact named Gravitre PCM write two zero two six "
        "with email gravitre pcm write two zero two six at alpha dot test "
        "dot gravitre dot app. Do not create it until I approve."
    )
    out = reconstitute_spoken_identity_fields(source)
    assert "gravitrepcmwrite2026@alpha.test.gravitre.app" in out.lower()
    assert "dot gravitre" not in out.lower()
    assert "named Gravitre PCM write 2026 with email" in out


def test_reconstitute_digit_word_run_does_not_touch_one_moment():
    from app.services.voice_session_service import reconstitute_spoken_identity_fields

    source = "One moment, look at this deal."
    assert reconstitute_spoken_identity_fields(source) == source


def test_reconstitute_spoken_email_does_not_rewrite_plain_at():
    from app.services.voice_session_service import reconstitute_spoken_identity_fields

    source = "Look at this HubSpot deal and tell me what changed."
    assert reconstitute_spoken_identity_fields(source) == source



def test_acoustic_short_audio_insufficient():
    # Tiny buffer → not ok
    result = extract_acoustic_features(b"\x00\x01")
    assert result["ok"] is False
