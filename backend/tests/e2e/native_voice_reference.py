"""Tool-free native Pipecat reference. Not imported by production.
Run only in an isolated acceptance environment with explicit live authorization.
"""
import os

def require_live_authorization():
    if os.getenv("GRAVITRE_REFERENCE_LIVE") != "1":
        raise RuntimeError("Reference live execution not authorized")
    for key in ("DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "REFERENCE_VOICE_ID", "REFERENCE_LLM_MODEL"):
        if not os.getenv(key, "").strip():
            raise RuntimeError("Missing reference configuration: " + key)

def build_reference(transport, stt, llm, tts):
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
    from pipecat.turns.user_turn_strategies import ExternalUserTurnStrategies
    context = LLMContext([{"role": "system", "content": "You are a conversational reference assistant. Respond naturally and briefly. You cannot access tools, accounts or business systems. Never claim to perform an external action."}])
    user, assistant = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(user_turn_strategies=ExternalUserTurnStrategies()))
    return PipelineTask(Pipeline([transport.input(), stt, user, llm, tts, transport.output(), assistant]), params=PipelineParams(enable_metrics=True, enable_usage_metrics=True))

async def bot(runner_args):
    require_live_authorization()
    from pipecat.runner.types import SmallWebRTCRunnerArguments
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
    from pipecat.transports.base_transport import TransportParams
    from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.pipeline.runner import PipelineRunner
    if not isinstance(runner_args, SmallWebRTCRunnerArguments):
        raise RuntimeError("Reference accepts native WebRTC only")
    transport = SmallWebRTCTransport(webrtc_connection=runner_args.webrtc_connection, params=TransportParams(audio_in_enabled=True, audio_out_enabled=True))
    stt = DeepgramFluxSTTService(api_key=os.environ["DEEPGRAM_API_KEY"], model="flux-general-en", should_interrupt=True)
    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"], settings=OpenAILLMService.Settings(model=os.environ["REFERENCE_LLM_MODEL"]))
    tts = ElevenLabsTTSService(api_key=os.environ["ELEVENLABS_API_KEY"], voice_id=os.environ["REFERENCE_VOICE_ID"], model="eleven_flash_v2_5", auto_mode=True)
    task = build_reference(transport, stt, llm, tts)
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.cancel()
    await PipelineRunner(handle_sigint=False).run(task)

if __name__ == "__main__":
    require_live_authorization()
    # The upstream dev runner is not an authenticated production service.
    # Only launch in a private, isolated acceptance environment.
    from pipecat.runner.run import main
    main()
