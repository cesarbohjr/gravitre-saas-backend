"""Per-tier voice delivery and spoken aliases.

Light turns get a livelier ElevenLabs delivery and deep turns a steadier one,
changed only when the tier's value differs from what is applied. Written
shorthand is said the way a person would say it.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pipecat.frames.frames import TTSUpdateSettingsFrame

from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.spoken_pronunciations import apply_spoken_aliases
from app.services.tier1_voice_service import (
    CONVERSATIONAL_VOICE_SETTINGS,
    VOICE_TIER_STABILITY,
    voice_stability_for_tier,
)


def _service(**settings: object) -> GravitreCognitiveLLMService:
    service = GravitreCognitiveLLMService(
        app_settings=SimpleNamespace(**settings),
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
    )
    service.push_frame = AsyncMock()
    return service


def _stabilities(service: GravitreCognitiveLLMService) -> list[float]:
    return [
        call.args[0].delta.stability
        for call in service.push_frame.await_args_list
        if isinstance(call.args[0], TTSUpdateSettingsFrame)
    ]


def test_medium_is_the_pipeline_baseline() -> None:
    assert VOICE_TIER_STABILITY["medium"] == CONVERSATIONAL_VOICE_SETTINGS["stability"]
    assert VOICE_TIER_STABILITY["light"] < VOICE_TIER_STABILITY["medium"] < VOICE_TIER_STABILITY["deep"]
    assert voice_stability_for_tier(None) == CONVERSATIONAL_VOICE_SETTINGS["stability"]
    assert voice_stability_for_tier("bogus") == CONVERSATIONAL_VOICE_SETTINGS["stability"]


def test_delivery_changes_only_when_the_tier_needs_it() -> None:
    service = _service()

    async def _run() -> None:
        for tier in ("medium", "light", "light", "deep", "deep", "medium"):
            await service._apply_tier_voice(tier)

    asyncio.run(_run())
    assert _stabilities(service) == [
        VOICE_TIER_STABILITY["light"],
        VOICE_TIER_STABILITY["deep"],
        VOICE_TIER_STABILITY["medium"],
    ]


def test_delivery_tuning_can_be_turned_off() -> None:
    service = _service(voice_tier_expression=False)
    asyncio.run(service._apply_tier_voice("light"))
    assert _stabilities(service) == []


def test_spoken_aliases_expand_shorthand() -> None:
    assert apply_spoken_aliases("Use text, e.g. reminders.") == "Use text, for example reminders."
    assert apply_spoken_aliases("Text vs. email") == "Text versus email"
    assert apply_spoken_aliases("Sales & marketing w/o approval") == "Sales and marketing without approval"
    # Inside a word or acronym, nothing changes.
    assert apply_spoken_aliases("Q&A and R&D") == "Q&A and R&D"
    assert apply_spoken_aliases("vsx stays") == "vsx stays"


def test_custom_aliases_come_from_settings_and_bad_json_is_ignored() -> None:
    assert apply_spoken_aliases("Gravitre is ready.", '{"Gravitre": "Grav-ih-tray"}') == "Grav-ih-tray is ready."
    assert apply_spoken_aliases("Gravitre is ready.", "not json") == "Gravitre is ready."


def test_tts_sanitizer_applies_aliases() -> None:
    service = _service(voice_spoken_aliases='{"Gravitre": "Grav-ih-tray"}')
    assert service._sanitize_for_tts("Gravitre can help, e.g. with leads") == (
        "Grav-ih-tray can help, for example with leads."
    )
