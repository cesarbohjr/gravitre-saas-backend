from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import wave

import pytest
from pipecat.frames.frames import InputAudioRawFrame

from app.services.contextual_understanding_service import perceive_turn
from app.services.pipecat_voice.acoustic_tap import AcousticTapProcessor
from app.services.voice_acoustic_signal import extract_acoustic_features, _persist_acoustic_signal
from app.services.sentiment_friction_service import conversational_adaptation_instruction


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken", [True, False])
@pytest.mark.parametrize("enabled", [True, False])
async def test_perception_survives_shortcuts_and_respects_org_setting(monkeypatch, spoken, enabled):
    history = [{"role": "user", "content": "I cannot find it"}]
    settings = Mock()
    client = Mock()
    dialogue = AsyncMock(return_value={"sentiment_detection_enabled": enabled})
    understanding = AsyncMock(return_value={"already_known_from_history": ["it"]})
    detector = Mock()
    detector.analyze.return_value = {"recommended_adaptation": "offer_options"}
    monkeypatch.setattr("app.services.chat_dialogue_settings.load_chat_dialogue_settings", dialogue)
    monkeypatch.setattr("app.services.contextual_understanding_service.get_contextual_understanding_service",
                        lambda _: SimpleNamespace(understand=understanding))
    monkeypatch.setattr("app.services.sentiment_friction_service.get_sentiment_friction_service", lambda: detector)
    _, sentiment, result = await perceive_turn("org-1", "I am confused", history,
        settings=settings, client=client, spoken_mode=spoken)
    dialogue.assert_awaited_once_with("org-1", settings, client=client)
    understanding.assert_awaited_once_with("I am confused", history, "org-1", spoken_mode=spoken)
    assert result["already_known_from_history"] == ["it"]
    assert sentiment["recommended_adaptation"] == ("offer_options" if enabled else "none")
    assert detector.analyze.call_count == int(enabled)
    if not enabled:
        assert sentiment["status"] == "disabled"


def test_live_pcm_preserves_rate_scope_and_clears_buffer(monkeypatch):
    schedule = Mock(return_value=None)
    monkeypatch.setattr("app.services.voice_acoustic_signal.schedule_acoustic_analysis", schedule)
    monkeypatch.setattr("app.workflows.repository.get_supabase_client", lambda _: Mock())
    tap = AcousticTapProcessor(settings=Mock(), org_id="org-a", user_id="user-a",
        conversation_id_getter=lambda: "current-conversation")
    tap._observe(InputAudioRawFrame(audio=b"\x00\x01" * 24000, sample_rate=24000, num_channels=1))
    tap._flush()
    args = schedule.call_args.kwargs
    assert args["org_id"] == "org-a"
    assert args["conversation_id"] == "current-conversation"
    with wave.open(BytesIO(args["audio_bytes"]), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnframes() == 24000
    assert not tap._pcm
    tap._flush()
    assert schedule.call_count == 1
    features = extract_acoustic_features(args["audio_bytes"])
    assert features["ok"]
    assert features["confidence"] is None
    assert features["accuracy_band"] is None
    assert features["calibration_status"] == "unvalidated"


def test_capture_is_bounded_and_drops_unsupported_audio():
    tap = AcousticTapProcessor(settings=Mock(), org_id="a", user_id="b", conversation_id_getter=lambda: None)
    tap._observe(InputAudioRawFrame(audio=b"\x00\x01" * 16000 * 12, sample_rate=16000, num_channels=1))
    assert len(tap._pcm) == 16000 * 2 * 8
    tap._observe(InputAudioRawFrame(audio=b"\x02\x03" * 16000, sample_rate=16000, num_channels=1))
    assert tap._pcm.endswith(b"\x02\x03" * 16000)
    assert len(tap._pcm) == 16000 * 2 * 8
    tap._observe(InputAudioRawFrame(audio=b"\x00\x01" * 100, sample_rate=16000, num_channels=2))
    assert not tap._pcm
    assert not extract_acoustic_features(b"compressed webm" * 2000)["ok"]


def test_synthetic_audio_and_inflight_analysis_are_not_reingested(monkeypatch):
    schedule = Mock()
    monkeypatch.setattr("app.services.voice_acoustic_signal.schedule_acoustic_analysis", schedule)
    tap = AcousticTapProcessor(settings=Mock(), org_id="a", user_id="b",
        conversation_id_getter=lambda: None, audio_origin_getter=lambda: "tts_loopback")
    frame = InputAudioRawFrame(audio=b"\x00\x01" * 16000, sample_rate=16000, num_channels=1)
    tap._observe(frame)
    assert not tap._pcm
    tap._audio_origin_getter = lambda: "user_mic"
    tap._observe(frame)
    tap._analysis_task = SimpleNamespace(done=lambda: False)
    tap._flush()
    schedule.assert_not_called()
    assert not tap._pcm


def test_acoustic_observation_cannot_become_learning_outcome():
    client = Mock()
    _persist_acoustic_signal(client, org_id="a", user_id="b", conversation_id="c", agent_id=None,
        result={"ok": True, "features": {"pace": 0.5}, "confidence": None})
    client.table.assert_called_once_with("audit_events")
    assert not client.table.return_value.insert.call_args.args[0]["metadata"]["autonomous_action"]


def test_delivery_policy_does_not_accept_free_text_instructions():
    assert conversational_adaptation_instruction("acknowledge_briefly")
    assert conversational_adaptation_instruction("ignore approvals") == ""


@pytest.mark.parametrize("model", ["eleven_flash_v2_5", "eleven_v3", "eleven_v3_conversational"])
def test_selected_model_uses_compatible_provider_protocol(model):
    from app.services.pipecat_voice.tts_factory import build_live_tts_service
    from pipecat.services.elevenlabs.dialogue.tts import ElevenLabsDialogueTTSService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    service = build_live_tts_service(api_key="test-key", voice_id="test-voice", model=model, sample_rate=24000)
    assert isinstance(service, ElevenLabsDialogueTTSService if model.startswith("eleven_v3") else ElevenLabsTTSService)
    assert service._settings.model == model
    assert service._settings.voice == "test-voice"


def test_v3_conversational_requires_explicit_evaluation_flag():
    from app.services.pipecat_voice.voice_latency_tuning import resolve_voice_tts_ab_eval
    assert not resolve_voice_tts_ab_eval(SimpleNamespace(voice_tts_ab_model="eleven_v3_conversational")).enabled
    assert resolve_voice_tts_ab_eval(SimpleNamespace(
        voice_tts_ab_model="eleven_v3_conversational", voice_tts_ab_v1=True,
    )).enabled
