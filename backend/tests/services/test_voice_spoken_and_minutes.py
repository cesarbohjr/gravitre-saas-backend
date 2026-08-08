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
from app.services.voice_session_service import split_speakable_chunks


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


def test_acoustic_short_audio_insufficient():
    # Tiny buffer → not ok
    result = extract_acoustic_features(b"\x00\x01")
    assert result["ok"] is False
