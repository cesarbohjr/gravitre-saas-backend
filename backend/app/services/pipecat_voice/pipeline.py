"""Build the Pipecat pipeline: transport → STT → speculative → Cognitive → ElevenLabs."""
from __future__ import annotations

from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from app.core.logging import get_logger
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from app.services.pipecat_voice.stt_factory import STT_FLUX, build_pipecat_stt
from app.services.pipecat_voice.text_turn_kick import TextTurnKickProcessor
from app.services.tier1_voice_service import resolve_voice_id

logger = get_logger(__name__)


def _optional_silero_vad():
    """Silero for non-Flux STT; Flux owns native end-of-turn (omit VAD)."""
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.audio.vad.vad_analyzer import VADParams

        return SileroVADAnalyzer(params=VADParams(stop_secs=0.4))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pipecat_silero_vad_unavailable error=%s", exc)
        return None


def build_pipecat_voice_task(
    *,
    websocket: Any,
    settings: Any,
    org_id: str,
    user_id: str,
    agent: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    voice_key: str | None = None,
    stt_provider: str | None = None,
    stt_fallback_from: str | None = None,
    stt_fallback_reason: str | None = None,
) -> tuple[PipelineTask, dict[str, Any]]:
    """Construct a PipelineTask for one authenticated browser WebSocket session.

    Returns (task, session_meta) so the router can advertise STT/TTS honesty on ready.
    """
    dg_key = (settings.deepgram_api_key or "").strip()
    el_key = (settings.elevenlabs_api_key or "").strip()
    if not el_key:
        raise RuntimeError("ELEVENLABS_API_KEY required for Pipecat voice")

    _key, voice_id = resolve_voice_id(settings, voice_key)
    profile = (agent or {}).get("voice_profile") if isinstance(agent, dict) else None
    if isinstance(profile, dict) and profile.get("voice_id"):
        voice_id = str(profile.get("voice_id"))
    model = (
        (profile.get("tts_model") if isinstance(profile, dict) else None)
        or settings.elevenlabs_tts_model
        or "eleven_flash_v2_5"
    )
    # Live conversational path must stay on Flash v2.5 — never v3.
    model_l = str(model).strip().lower()
    if "eleven_v3" in model_l or model_l in {"eleven_multilingual_v2", "eleven_turbo_v2", "eleven_turbo_v2_5"}:
        model = "eleven_flash_v2_5"

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            audio_in_channels=1,
            audio_out_channels=1,
            serializer=GravitreJsonAudioSerializer(),
        ),
    )

    stt, stt_info = build_pipecat_stt(
        settings,
        provider=stt_provider,
        fallback_from=stt_fallback_from,
        fallback_reason=stt_fallback_reason,
    )
    if stt_info.get("stt_provider_key") != STT_FLUX and not dg_key and stt_info.get("stt_provider_key") != "openai":
        raise RuntimeError("DEEPGRAM_API_KEY required for Pipecat voice")

    speculative = SpeculativePrefetchProcessor(
        app_settings=settings,
        org_id=org_id,
        user_id=user_id,
    )
    llm = GravitreCognitiveLLMService(
        app_settings=settings,
        org_id=org_id,
        user_id=user_id,
        agent=agent,
        conversation_id=conversation_id,
    )
    tts = ElevenLabsTTSService(
        api_key=el_key,
        voice_id=voice_id,
        model=str(model),
        sample_rate=16000,
        auto_mode=True,
    )

    use_flux = stt_info.get("stt_provider_key") == STT_FLUX
    # Flux: native EOT — do not stack Silero VAD turn machine alongside it.
    vad = None if use_flux else _optional_silero_vad()
    context = LLMContext()
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            TextTurnKickProcessor(),
            speculative,
            user_agg,
            llm,
            tts,
            transport.output(),
            assistant_agg,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    session_meta = {
        "architecture": "pipecat_deepgram_cognitive_elevenlabs",
        "cognitive_path": "CognitiveTurnKernel",
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "org_id": org_id,
        "conversation_id": conversation_id,
        "tts_model": str(model),
        "tts_transport": "websocket",
        **stt_info,
    }

    @transport.event_handler("on_client_connected")
    async def _on_client_connected(_transport, _websocket):
        # Emit after the receive loop is up so early text ingress is not dropped.
        try:
            await websocket.send_json({"type": "session.ready", **session_meta})
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_session_ready_send_failed error=%s", exc)

    return task, session_meta
