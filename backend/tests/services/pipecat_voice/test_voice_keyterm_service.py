"""Tests for Voice 3.0 Phase 3 keyterms and Flux turn-mode presets."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.pipecat_voice.voice_keyterm_service import (
    build_voice_keyterms,
    resolve_flux_eot_settings,
    resolve_flux_turn_mode_label,
)
from app.services.tier1_voice_service import voice_status


def test_build_voice_keyterms_disabled():
    terms, meta = build_voice_keyterms(enabled=False, org_name="Acme")
    assert terms == []
    assert meta["keyterms_enabled"] is False
    assert meta["keyterm_count"] == 0


def test_build_voice_keyterms_includes_org_agent_and_connectors():
    terms, meta = build_voice_keyterms(
        enabled=True,
        org_name="Acme Corp",
        agent={"name": "Jordan Sales", "department": "sales"},
        connected_integrations=["hubspot", "salesforce"],
        max_terms=50,
    )
    assert "Gravitre" in terms
    assert "Acme Corp" in terms
    assert "Jordan Sales" in terms
    assert "HubSpot" in terms
    assert "Salesforce" in terms
    assert "pipeline" in terms
    assert meta["keyterm_count"] == len(terms)
    assert "org_name" in meta["keyterm_sources"]
    assert "connected_integrations" in meta["keyterm_sources"]


def test_build_voice_keyterms_dedupes_and_caps():
    terms, meta = build_voice_keyterms(
        enabled=True,
        org_name="Gravitre",
        agent={"name": "Gravitre"},
        connected_integrations=["hubspot", "hubspot"],
        max_terms=8,
    )
    assert len(terms) <= 8
    assert meta["keyterm_count"] == len(terms)
    assert terms.count("Gravitre") == 1


def test_resolve_flux_eot_settings_turn_mode_preset():
    settings = SimpleNamespace(
        voice_flux_turn_mode="fast",
        voice_pipecat_flux_eager_eot=0.5,
        voice_pipecat_flux_eot=0.7,
    )
    eager, eot = resolve_flux_eot_settings(settings)
    assert eager == 0.4
    assert eot == 0.55
    assert resolve_flux_turn_mode_label(settings) == "fast"


def test_resolve_flux_eot_settings_env_when_no_mode():
    settings = SimpleNamespace(
        voice_flux_turn_mode=None,
        voice_pipecat_flux_eager_eot=0.55,
        voice_pipecat_flux_eot=0.75,
    )
    eager, eot = resolve_flux_eot_settings(settings)
    assert eager == 0.55
    assert eot == 0.75


def test_voice_status_exposes_phase3_turn_stt():
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
            voice_keyterms_v1=True,
            voice_keyterms_max=40,
            voice_flux_turn_mode="patient",
            voice_pipecat_flux_eager_eot=0.5,
            voice_pipecat_flux_eot=0.7,
        )
    )
    p3 = status["phase3_turn_stt"]
    assert p3["keyterms_v1"] is True
    assert p3["keyterms_max"] == 40
    assert p3["flux_turn_mode"] == "patient"
    assert p3["flux_eager_eot"] == 0.6
    assert p3["flux_eot"] == 0.85
