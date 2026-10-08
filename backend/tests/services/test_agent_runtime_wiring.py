"""Agent row fields, voice precedence/STT settings, and knowledge assignment parsing."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.operators.agent_prompts import agent_list_field, build_agent_instructions_section
from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService
from app.services.handoff_service import get_agent
from app.services.pipecat_voice.pipeline import resolve_voice_and_tts_model
from app.services.pipecat_voice.stt_factory import STT_FLUX, STT_NOVA3, build_pipecat_stt
from app.services.pipecat_voice.voice_keyterm_service import FLUX_TURN_PRESETS
from app.services.voice_agent_profile import resolve_session_voice


# --- agents row ---------------------------------------------------------------


def test_get_agent_selects_skills_guardrails_and_voice_profile():
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "a1", "capabilities": ["crm"], "guardrails": ["no pii"], "voice_profile": {}}]
    )
    row = get_agent(client, "org-1", "a1")
    columns = {c.strip() for c in client.table.return_value.select.call_args.args[0].split(",")}
    assert {"capabilities", "guardrails", "voice_profile", "config", "purpose"} <= columns
    assert row is not None and row["capabilities"] == ["crm"]


def test_agent_list_field_handles_strings_and_objects():
    agent = {"guardrails": ["No PII", {"name": "Approval for sends"}, {"name": "off", "enabled": False}, ""]}
    assert agent_list_field(agent, "guardrails") == ["No PII", "Approval for sends"]
    assert agent_list_field({"guardrails": "nope"}, "guardrails") == []


def test_agent_instructions_section_empty_for_bare_agent():
    assert build_agent_instructions_section({"id": "a1", "name": "x"}) == ""


# --- voice precedence ---------------------------------------------------------


class _VoiceSettings:
    elevenlabs_default_voice = "sarah"
    elevenlabs_tts_model = "eleven_flash_v2_5"
    elevenlabs_voice_sarah = ""
    elevenlabs_voice_rachel = ""
    elevenlabs_voice_adam = ""
    elevenlabs_voice_josh = ""
    elevenlabs_voice_eric = ""


def test_session_voice_agent_profile_wins_over_request():
    agent = {"voice_profile": {"voice_id": "agent-voice-id-123456"}}
    assert resolve_session_voice(agent, "picker-voice") == "agent-voice-id-123456"
    assert resolve_session_voice({"voice_profile": {"voice_key": "adam"}}, "rachel") == "adam"


def test_session_voice_falls_back_to_request_then_default():
    assert resolve_session_voice({"voice_profile": {}}, "rachel") == "rachel"
    assert resolve_session_voice({"id": "a1"}, None) is None
    assert resolve_session_voice(None, "  ") is None


def test_pipeline_voice_uses_agent_voice_key_over_request():
    from app.services.tier1_voice_service import resolve_voice_id

    _, expected = resolve_voice_id(_VoiceSettings(), "adam")
    voice_id, _model = resolve_voice_and_tts_model(
        _VoiceSettings(), agent={"voice_profile": {"voice_key": "adam"}}, voice_key="rachel"
    )
    assert voice_id == expected


def test_pipeline_voice_agent_without_profile_uses_requested_voice():
    from app.services.tier1_voice_service import resolve_voice_id

    _, expected = resolve_voice_id(_VoiceSettings(), "rachel")
    voice_id, _model = resolve_voice_and_tts_model(_VoiceSettings(), agent={"id": "a1"}, voice_key="rachel")
    assert voice_id == expected


# --- Deepgram STT from voice_profile -----------------------------------------------


def _stt_settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        deepgram_api_key="dg-test",
        voice_pipecat_stt_provider=provider,
        voice_stt_provider=provider,
        pipecat_stt_provider=provider,
        voice_flux_turn_mode=None,
        voice_pipecat_flux_eager_eot=None,
        voice_pipecat_flux_eot=None,
    )


def test_nova3_receives_agent_language():
    captured = {}

    class FakeDeepgram:
        class Settings:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        def __init__(self, **kwargs):
            pass

    with patch("pipecat.services.deepgram.stt.DeepgramSTTService", FakeDeepgram), patch(
        "app.services.pipecat_voice.stt_factory.resolve_pipecat_stt_provider", return_value=STT_NOVA3
    ):
        _stt, meta = build_pipecat_stt(_stt_settings("nova3"), language="es")
    assert str(getattr(captured["language"], "value", captured["language"])) == "es"
    assert meta["stt_language"] == "es"


def test_non_english_agent_routes_flux_to_nova3():
    class FakeDeepgram:
        class Settings:
            def __init__(self, **kwargs):
                pass

        def __init__(self, **kwargs):
            pass

    with patch("pipecat.services.deepgram.stt.DeepgramSTTService", FakeDeepgram), patch(
        "app.services.pipecat_voice.stt_factory.resolve_pipecat_stt_provider", return_value=STT_FLUX
    ):
        _stt, meta = build_pipecat_stt(_stt_settings("flux"), language="fr")
    assert meta["stt_provider_key"] == STT_NOVA3
    assert meta["stt_language_routed_from"] == STT_FLUX


def test_flux_turn_sensitivity_applies_preset():
    captured = {}

    class FakeFlux:
        class Settings:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        def __init__(self, **kwargs):
            pass

    with patch("pipecat.services.deepgram.flux.stt.DeepgramFluxSTTService", FakeFlux), patch(
        "app.services.pipecat_voice.stt_factory.resolve_pipecat_stt_provider", return_value=STT_FLUX
    ):
        _stt, meta = build_pipecat_stt(_stt_settings("flux"), language="en", turn_sensitivity="patient")
    eager, eot = FLUX_TURN_PRESETS["patient"]
    assert captured["eager_eot_threshold"] == eager
    assert captured["eot_threshold"] == eot
    assert meta["stt_turn_sensitivity"] == "patient"


def test_flux_eager_threshold_turns_on_eager_end_of_turn():
    captured_service = {}

    class FakeFlux:
        class Settings:
            def __init__(self, **kwargs):
                pass

        def __init__(self, **kwargs):
            captured_service.update(kwargs)

    with patch("pipecat.services.deepgram.flux.stt.DeepgramFluxSTTService", FakeFlux), patch(
        "app.services.pipecat_voice.stt_factory.resolve_pipecat_stt_provider", return_value=STT_FLUX
    ):
        _stt, meta = build_pipecat_stt(_stt_settings("flux"), language="en", turn_sensitivity="patient")
    assert captured_service["enable_eager_end_of_turn"] is True
    assert meta["stt_eager_end_of_turn"] is True


def test_flux_normal_sensitivity_keeps_deployment_thresholds():
    captured = {}

    class FakeFlux:
        class Settings:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        def __init__(self, **kwargs):
            pass

    with patch("pipecat.services.deepgram.flux.stt.DeepgramFluxSTTService", FakeFlux), patch(
        "app.services.pipecat_voice.stt_factory.resolve_pipecat_stt_provider", return_value=STT_FLUX
    ):
        _stt, meta = build_pipecat_stt(_stt_settings("flux"), turn_sensitivity="normal")
    assert "eot_threshold" not in captured
    assert "stt_turn_sensitivity" not in meta


# --- knowledge assignments ------------------------------------------------------------


def test_resolve_assignments_accepts_string_packs_and_datasets():
    svc = AgentKnowledgeAssignmentService(settings=SimpleNamespace())
    rows = svc.resolve_assignments(
        {
            "id": "a1",
            "config": {
                "knowledge_packs": ["pack.sales.core", {"id": "pack.hr.policy", "name": "HR"}, "  "],
                "datasets": ["ds-123"],
            },
        }
    )
    pairs = [(row["sourceType"], row["sourceId"]) for row in rows]
    assert pairs == [
        ("knowledge_pack", "pack.sales.core"),
        ("knowledge_pack", "pack.hr.policy"),
        ("dataset", "ds-123"),
    ]
    assert all(row["fromConfig"] for row in rows)


def test_assigned_pack_ids_reads_camel_and_snake_rows():
    rows = [
        {"sourceType": "knowledge_pack", "sourceId": "pack.a", "enabled": True},
        {"source_type": "knowledge_pack", "source_id": "pack.b"},
        {"sourceType": "knowledge_pack", "sourceId": "pack.c", "enabled": False},
        {"sourceType": "folder", "sourceId": "pack.d"},
        {"sourceType": "knowledge_pack", "sourceId": "custom-pack"},
    ]
    assert AgentKnowledgeAssignmentService.assigned_pack_ids(rows) == ["pack.a", "pack.b"]
