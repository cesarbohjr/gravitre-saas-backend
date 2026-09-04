"""Build the Pipecat pipeline: transport → Deepgram → speculative → Cognitive → ElevenLabs."""
from __future__ import annotations

from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from app.core.logging import get_logger
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from app.services.pipecat_voice.text_turn_kick import TextTurnKickProcessor
from app.services.tier1_voice_service import resolve_voice_id

logger = get_logger(__name__)


def _optional_silero_vad():
    """Silero improves barge-in; omit if onnx/model unavailable on the host."""
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
) -> PipelineTask:
    """Construct a PipelineTask for one authenticated browser WebSocket session."""
    dg_key = (settings.deepgram_api_key or "").strip()
    el_key = (settings.elevenlabs_api_key or "").strip()
    if not dg_key:
        raise RuntimeError("DEEPGRAM_API_KEY required for Pipecat voice")
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

    stt = DeepgramSTTService(api_key=dg_key)
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
    )

    context = LLMContext()
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=_optional_silero_vad(),
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

    @transport.event_handler("on_client_connected")
    async def _on_client_connected(_transport, _websocket):
        # Emit after the receive loop is up so early text ingress is not dropped.
        try:
            await websocket.send_json(
                {
                    "type": "session.ready",
                    "architecture": "pipecat_deepgram_cognitive_elevenlabs",
                    "cognitive_path": "CognitiveTurnKernel",
                    "write_confirm_policy": "nl_yes_same_path_as_text",
                    "org_id": org_id,
                    "conversation_id": conversation_id,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_session_ready_send_failed error=%s", exc)

    return task
