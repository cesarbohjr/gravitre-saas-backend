"""Standing safeguard (Phase 4, 2026-09-06 voice regression investigation).

Live user report: "voice reverted to sounding robotic" immediately after the
llm_first_token optimization pass. The Phase 0 reconciliation for that
investigation ruled out a TTS/model regression in *this* pass (no commit in
the window touched `pipecat_voice/pipeline.py` at all — confirmed via
`git log`), but the investigation exposed a real, standing gap: nothing in
CI actually pins that live conversational voice always resolves to
`eleven_flash_v2_5`, regardless of settings drift, an agent's stored
voice_profile, or a future context-reduction/complexity-tiering change that
touches model routing. A future change *could* silently swap a lower-quality
model in and nothing would catch it before deploy — exactly the class of gap
this program has repeatedly found and closed after Cesar had to notice a
live quality regression himself.

This test pins `resolve_voice_and_tts_model` (the extracted, directly
testable resolution + guard-rail logic backing `build_pipecat_voice_task`)
so any future change that lets a disallowed model (v3, multilingual_v2,
turbo_v2, turbo_v2_5) reach the live conversational path fails CI, before
a deploy, not after Cesar notices the voice sounds wrong.
"""
from __future__ import annotations

from app.services.pipecat_voice.pipeline import (
    DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS,
    SAFE_LIVE_CONVERSATIONAL_TTS_MODEL,
    resolve_voice_and_tts_model,
)


class _Settings:
    def __init__(self, *, elevenlabs_tts_model: str = "eleven_flash_v2_5") -> None:
        self.elevenlabs_default_voice = "rachel"
        self.elevenlabs_tts_model = elevenlabs_tts_model
        self.elevenlabs_voice_rachel = ""
        self.elevenlabs_voice_adam = ""
        self.elevenlabs_voice_josh = ""


class TestDefaultResolutionStaysOnFlash:
    def test_no_override_anywhere_resolves_to_flash(self) -> None:
        """MUTATION PROOF: change the default fallback in
        `resolve_voice_and_tts_model` (or `SAFE_LIVE_CONVERSATIONAL_TTS_MODEL`
        itself) away from Flash v2.5 and this fails.
        """
        _voice_id, model = resolve_voice_and_tts_model(
            _Settings(), agent=None, voice_key=None
        )
        assert model == SAFE_LIVE_CONVERSATIONAL_TTS_MODEL == "eleven_flash_v2_5"

    def test_blank_settings_model_falls_back_to_flash_not_none(self) -> None:
        _voice_id, model = resolve_voice_and_tts_model(
            _Settings(elevenlabs_tts_model=""), agent=None, voice_key=None
        )
        assert model == "eleven_flash_v2_5"


class TestGuardRailBlocksDisallowedModels:
    def test_settings_level_v3_is_downgraded_to_flash(self) -> None:
        """MUTATION PROOF: remove the `"eleven_v3" in model_l` check and this
        fails — a v3 model configured at the settings/env level would reach
        the live conversational path unguarded.
        """
        _voice_id, model = resolve_voice_and_tts_model(
            _Settings(elevenlabs_tts_model="eleven_v3"), agent=None, voice_key=None
        )
        assert model == "eleven_flash_v2_5"

    def test_agent_voice_profile_v3_override_is_also_downgraded(self) -> None:
        """The guard-rail must apply regardless of *where* the disallowed
        model came from — an agent's stored `voice_profile.tts_model` is a
        genuine, real override path (per-agent voice customization), not a
        hardcoded constant, so it must be checked too, not just the settings
        default.
        """
        _voice_id, model = resolve_voice_and_tts_model(
            _Settings(),
            agent={"voice_profile": {"tts_model": "eleven_v3"}},
            voice_key=None,
        )
        assert model == "eleven_flash_v2_5"

    def test_every_named_disallowed_model_is_downgraded(self) -> None:
        """MUTATION PROOF: shrink `DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS`
        and whichever entry was removed stops being downgraded — this test
        iterates the real, current set, not a hardcoded copy of it, so it
        stays correct as the set is intentionally edited, but still fails if
        the downgrade logic itself breaks.
        """
        assert DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS, (
            "the disallowed-model set must not be empty — an empty set here "
            "would make every test in this class vacuously pass"
        )
        for disallowed in DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS:
            _voice_id, model = resolve_voice_and_tts_model(
                _Settings(elevenlabs_tts_model=disallowed), agent=None, voice_key=None
            )
            assert model == "eleven_flash_v2_5", f"{disallowed!r} was not downgraded"

    def test_case_and_whitespace_insensitive_guard(self) -> None:
        """A real config value could plausibly arrive with different casing
        or stray whitespace (env var copy-paste, admin UI free-text field) —
        the guard must not be bypassable by that alone.
        """
        _voice_id, model = resolve_voice_and_tts_model(
            _Settings(elevenlabs_tts_model="  ELEVEN_V3  "),
            agent=None,
            voice_key=None,
        )
        assert model == "eleven_flash_v2_5"


class TestVoiceIdOverrideIsHonored:
    def test_agent_voice_profile_voice_id_override_is_used(self) -> None:
        """This is a genuine, deliberate per-agent customization path, not a
        regression — must keep working (not part of the guard-rail).
        """
        voice_id, _model = resolve_voice_and_tts_model(
            _Settings(),
            agent={"voice_profile": {"voice_id": "custom-voice-123"}},
            voice_key=None,
        )
        assert voice_id == "custom-voice-123"
