"""Voice 3.0 Phase 4 — latency tuning tests."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.pipecat_voice.speculative_generation import (
    SpeculativeGenerationCoordinator,
    start_speculative_run,
)
from app.services.pipecat_voice.voice_latency_tuning import (
    resolve_voice_speculative_tuning,
    resolve_voice_tts_ab_eval,
    resolve_voice_tts_chunk_tuning,
    speculative_interim_materially_changed,
)
from app.services.tier1_voice_service import voice_status
from app.services.voice_session_service import split_speakable_chunks


def test_resolve_voice_speculative_tuning_defaults_off():
    tuning = resolve_voice_speculative_tuning(SimpleNamespace())
    assert tuning.v2_enabled is False
    assert tuning.min_chars == 8
    assert tuning.prefix_adopt is False


def test_resolve_voice_speculative_tuning_v2_on():
    tuning = resolve_voice_speculative_tuning(
        SimpleNamespace(
            voice_speculative_v2=True,
            voice_speculative_min_chars=6,
            voice_speculative_prefix_adopt=True,
            voice_speculative_prefix_max_words=2,
        )
    )
    assert tuning.v2_enabled is True
    assert tuning.min_chars == 6
    assert tuning.prefix_adopt is True
    assert tuning.prefix_max_extra_words == 2


def test_resolve_voice_tts_chunk_tuning_v2_defaults_to_eight():
    tuning = resolve_voice_tts_chunk_tuning(SimpleNamespace(voice_tts_chunk_v2=True))
    assert tuning.v2_enabled is True
    assert tuning.min_chars == 8


@pytest.mark.asyncio
async def test_speculative_prefix_adopt_extends_partial():
    coordinator = SpeculativeGenerationCoordinator()

    async def _runner():
        yield "ok"

    run = start_speculative_run(
        text="what is two plus two",
        runner=_runner,
        create_task=asyncio.ensure_future,
    )
    coordinator.set_run(run)
    await run.task

    adopted = coordinator.adopt("what is two plus two please", prefix_max_extra_words=3)
    assert adopted is not None


@pytest.mark.asyncio
async def test_speculative_prefix_adopt_rejects_large_extension():
    coordinator = SpeculativeGenerationCoordinator()

    async def _runner():
        yield "ok"

    run = start_speculative_run(
        text="what is two plus two",
        runner=_runner,
        create_task=asyncio.ensure_future,
    )
    coordinator.set_run(run)
    await run.task

    adopted = coordinator.adopt(
        "what is two plus two and also explain calculus",
        prefix_max_extra_words=2,
    )
    assert adopted is None


def test_speculative_interim_extension_not_material_change():
    assert speculative_interim_materially_changed("what is two", "what is two plus") is False


def test_speculative_interim_revision_is_material_change():
    assert speculative_interim_materially_changed("email sarah", "email mike") is True


def test_split_speakable_chunks_aggressive_flushes_earlier():
    ready_default, _ = split_speakable_chunks("Two plus two equals", min_chars=12, aggressive=False)
    ready_aggressive, _ = split_speakable_chunks("Two plus two equals", min_chars=8, aggressive=True)
    assert ready_default
    assert ready_aggressive


def test_resolve_voice_tts_ab_eval_requires_allowlist():
    off = resolve_voice_tts_ab_eval(
        SimpleNamespace(voice_tts_ab_v1=True, voice_tts_ab_model="eleven_flash_v2_5")
    )
    assert off.enabled is False
    on = resolve_voice_tts_ab_eval(
        SimpleNamespace(voice_tts_ab_v1=True, voice_tts_ab_model="eleven_v3")
    )
    assert on.enabled is True
    assert on.model == "eleven_v3"


def test_voice_status_exposes_phase4_latency():
    status = voice_status(
        SimpleNamespace(
            elevenlabs_api_key="",
            deepgram_api_key="k",
            openai_api_key="",
            elevenlabs_default_voice="sarah",
            elevenlabs_tts_model="eleven_flash_v2_5",
            elevenlabs_voice_sarah="",
            elevenlabs_voice_rachel="",
            elevenlabs_voice_adam="",
            elevenlabs_voice_josh="",
            elevenlabs_voice_eric="",
            voice_pipecat_enabled=True,
            voice_pipecat_stt="flux",
            voice_pipecat_stt_fallback_enabled=True,
            voice_pipecat_stt_fallback="nova3",
            api_public_url="https://api.gravitre.app",
            voice_speculative_v2=True,
            voice_tts_chunk_v2=True,
            voice_tts_ab_v1=True,
            voice_tts_ab_model="eleven_v3",
        )
    )
    p4 = status["phase4_latency"]
    assert p4["speculative_v2"] is True
    assert p4["tts_chunk_v2"] is True
    assert p4["tts_ab_v1"] is True
    assert p4["tts_ab_model"] == "eleven_v3"
