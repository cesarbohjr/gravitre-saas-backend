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
from pipecat.turns.user_stop.external_user_turn_stop_strategy import (
    ExternalUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from app.core.logging import get_logger
from app.services.pipecat_voice.backchannel_turn_strategy import (
    BackchannelAwareUserTurnStartStrategy,
)
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService
from app.services.pipecat_voice.interrupt_reporter import ElevenLabsInterruptReporter
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer
from app.services.pipecat_voice.speculative_generation import SpeculativeGenerationCoordinator
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from app.services.pipecat_voice.stt_factory import STT_FLUX, build_pipecat_stt
from app.services.pipecat_voice.text_turn_kick import TextTurnKickProcessor
from app.services.pipecat_voice.tts_warmup import warm_elevenlabs_tts_connection
from app.services.pipecat_voice.voice_latency_metrics import record_voice_e2e_latency_sample
from app.services.pipecat_voice.voice_latency_observer import GravitreVoiceLatencyObserver
from app.services.tier1_voice_service import resolve_voice_id

logger = get_logger(__name__)


# Voice-quality standing safeguard (2026-09-06, live regression investigation):
# every model that is a genuine per-turn conversational speech risk if it were
# ever accidentally routed to. This is the guard-rail Flash v2.5 must never
# be silently swapped for on the live conversational path. Kept as a
# named, testable constant (not just inline logic) so a future change to
# this set is itself a reviewable diff, and `test_pipecat_voice_tts_model_guard.py`
# pins the resolution behavior around it in CI, before any deploy.
DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS: frozenset[str] = frozenset(
    {"eleven_multilingual_v2", "eleven_turbo_v2", "eleven_turbo_v2_5"}
)
SAFE_LIVE_CONVERSATIONAL_TTS_MODEL = "eleven_flash_v2_5"


def resolve_voice_and_tts_model(
    settings: Any, *, agent: dict[str, Any] | None, voice_key: str | None
) -> tuple[str, str]:
    """Resolve (voice_id, tts_model) for one Pipecat voice session.

    Pulled out of `build_pipecat_voice_task` (2026-09-06 regression
    investigation) so the model/voice resolution — including the "never v3
    live" guard-rail — is directly unit-testable without constructing a full
    pipeline/transport/websocket. This is the exact logic a future
    context-reduction, complexity-tiering, or provider-swap change would have
    to touch to accidentally route live conversational voice through a
    lower-quality synthesis path; pinning it here is this program's standing
    safeguard against that regression class recurring silently (Phase 4 of
    the 2026-09-06 investigation).
    """
    _key, voice_id = resolve_voice_id(settings, voice_key)
    profile = (agent or {}).get("voice_profile") if isinstance(agent, dict) else None
    if isinstance(profile, dict) and profile.get("voice_id"):
        voice_id = str(profile.get("voice_id"))
    model = (
        (profile.get("tts_model") if isinstance(profile, dict) else None)
        or settings.elevenlabs_tts_model
        or SAFE_LIVE_CONVERSATIONAL_TTS_MODEL
    )
    # Live conversational path must stay on Flash v2.5 — never v3.
    model_l = str(model).strip().lower()
    if "eleven_v3" in model_l or model_l in DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS:
        model = SAFE_LIVE_CONVERSATIONAL_TTS_MODEL
    return voice_id, str(model)


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

    voice_id, model = resolve_voice_and_tts_model(settings, agent=agent, voice_key=voice_key)

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
    use_flux = stt_info.get("stt_provider_key") == STT_FLUX

    # Voice-SLO follow-up (2026-09-05): shared LLMContext (so the speculative
    # path can read the same prior-turn history GravitreCognitiveLLMService
    # will eventually use) + one coordinator per session shared between the
    # two processors below. ProposedUserStoppedSpeakingFrame (the trigger for
    # speculative generation) is Flux-specific — no coordinator is wired for
    # non-Flux STT, so this is a genuine no-op there, not a silently-broken
    # feature.
    context = LLMContext()
    speculative_coordinator = SpeculativeGenerationCoordinator() if use_flux else None
    speculative = SpeculativePrefetchProcessor(
        app_settings=settings,
        org_id=org_id,
        user_id=user_id,
        agent=agent if isinstance(agent, dict) else None,
        conversation_id=conversation_id,
        llm_context=context,
        speculative_coordinator=speculative_coordinator,
    )
    llm = GravitreCognitiveLLMService(
        app_settings=settings,
        org_id=org_id,
        user_id=user_id,
        agent=agent,
        conversation_id=conversation_id,
        speculative_coordinator=speculative_coordinator,
    )
    tts = ElevenLabsTTSService(
        api_key=el_key,
        voice_id=voice_id,
        model=str(model),
        sample_rate=16000,
        auto_mode=True,
    )
    interrupt_reporter = ElevenLabsInterruptReporter()

    # Flux: native EOT — do not stack Silero VAD turn machine alongside it.
    vad = None if use_flux else _optional_silero_vad()
    user_params_kwargs: dict[str, Any] = {"vad_analyzer": vad}
    if use_flux:
        # Conversational-realism Phase 1 (backchannel vs. interruption):
        # Flux's own turn detection drives this via Proposed*SpeakingFrame,
        # normally resolved instantly by ExternalUserTurnStartStrategy
        # (Pipecat's stock behavior — confirmed live root cause of "agent
        # stops on every uh-huh"). Swap in the classifying strategy so a
        # short backchannel utterance overlapping agent speech never
        # triggers the barge-in; a real interruption/correction/question/
        # stop-command still does, matching Flux's own recommended
        # should_interrupt=True default (ExternalUserTurnStrategies).
        user_params_kwargs["user_turn_strategies"] = UserTurnStrategies(
            start=[BackchannelAwareUserTurnStartStrategy(enable_interruptions=True)],
            stop=[ExternalUserTurnStopStrategy()],
        )
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(**user_params_kwargs),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            TextTurnKickProcessor(),
            speculative,
            user_agg,
            llm,
            interrupt_reporter,
            tts,
            transport.output(),
            assistant_agg,
        ]
    )

    latency_observer = GravitreVoiceLatencyObserver()
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[latency_observer],
    )

    # on_latency_measured always fires (same synchronous handler call) just
    # before on_latency_breakdown for the same cycle — see
    # UserBotLatencyObserver._handle_bot_started_speaking. Stash it here so
    # one turn produces exactly one audit_events row, not two.
    _pending_e2e_ms: dict[str, int] = {}

    @latency_observer.event_handler("on_latency_measured")
    async def _on_voice_latency_measured(_observer, latency_seconds: float) -> None:
        _pending_e2e_ms["value"] = round(latency_seconds * 1000)

    @latency_observer.event_handler("on_latency_breakdown")
    async def _on_voice_latency_breakdown(_observer, breakdown) -> None:
        # Phase 6 (conversational-realism): real per-stage latency, one
        # sample per completed user->bot cycle. Fire-and-forget — must never
        # slow down or break the live voice turn it is reporting on.
        try:
            ttfb_by_processor_ms: dict[str, int] = {}
            for entry in breakdown.ttfb:
                key = str(entry.processor).split("#", 1)[0]
                ttfb_by_processor_ms[key] = round(entry.duration_secs * 1000)
            user_turn_finalization_ms = (
                round(breakdown.user_turn_secs * 1000)
                if breakdown.user_turn_secs is not None
                else None
            )
            record_voice_e2e_latency_sample(
                settings,
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                end_to_end_ms=_pending_e2e_ms.pop("value", None),
                user_turn_finalization_ms=user_turn_finalization_ms,
                ttfb_by_processor_ms=ttfb_by_processor_ms,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("pipecat_voice_latency_breakdown_sample_failed error=%s", exc)

    session_meta = {
        "architecture": "pipecat_deepgram_cognitive_elevenlabs",
        "cognitive_path": "CognitiveTurnKernel",
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "org_id": org_id,
        "conversation_id": conversation_id,
        "tts_model": str(model),
        "tts_transport": "websocket",
        "tts_warmup": "elevenlabs_ws_preconnect",
        "barge_in": "elevenlabs_interrupt_report",
        "speak_v2": False,
        "speak_v2_note": "N/A — live TTS is ElevenLabs Flash, not Deepgram Speak v2",
        "speculative_prefetch": "read_only_embed_knowledge_tool_docs",
        "speculative_generation": "probable_eot_cancelable_adopt_on_match" if use_flux else "disabled_non_flux_stt",
        **stt_info,
    }

    @transport.event_handler("on_client_connected")
    async def _on_client_connected(_transport, _websocket):
        # Emit after the receive loop is up so early text ingress is not dropped.
        try:
            await websocket.send_json({"type": "session.ready", **session_meta})
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_session_ready_send_failed error=%s", exc)
        # Silent TTS warm-up — preconnect WS, no audible opener text.
        try:
            warm = await warm_elevenlabs_tts_connection(tts)
            session_meta["tts_warmed"] = bool(warm.get("ok"))
            if warm.get("ok"):
                try:
                    await websocket.send_json(
                        {"type": "tts.warmed", "method": warm.get("method"), "ok": True}
                    )
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("pipecat_tts_warmup_hook_failed error=%s", exc)

    return task, session_meta
