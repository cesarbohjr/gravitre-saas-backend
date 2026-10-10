"""Local Pipecat voice server for the browser voice guard (playwright.voice.config.ts).

Runs the production pipeline builder, ``build_pipecat_voice_task``, on a real
FastAPI WebSocket. Everything between the browser and the providers is the
production code: the JSON/PCM serializer, the websocket transport, the Flux
turn strategies (backchannel-aware start, external stop), the speculative
processor, the Cognitive LLM bridge with durable history load and persistence,
the interrupt reporter and the spoken-text tap.

What is replaced, and why:
- Deepgram Flux STT → ``ScriptedFluxSTT``. It emits the same frames Flux emits
  (ProposedUserStarted/Stopped, interim and finalized transcripts), driven by
  how much PCM the browser has actually sent, so the turn only happens if
  browser capture reaches the server.
- ElevenLabs TTS → ``ToneTTS``, which synthesizes an audible tone per sentence.
- The reasoning model → a scripted ``execute_task_streaming``.
- Supabase → ``FakeSupabase`` (filters honoured), so persistence is observable.
- Auth, org resolution and the production router are not exercised; the
  socket is accepted without a token check.

Run from ``backend/``: ``python -m tests.e2e.pipecat_voice_harness_server --port 8799``.
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import uuid
from typing import Any, AsyncGenerator

# Settings must load, but nothing here may reach a real service: Supabase,
# Redis and the model are replaced below. Empty CI secrets count as unset.
for _key, _value in {
    "APP_ENV": "dev",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
    "SUPABASE_JWT_SECRET": "jwt-secret-test",
    "OPENAI_API_KEY": "sk-test-openai",
    # The guard asserts the exact reply; a slow CI runner would otherwise get
    # the deep-turn "one moment" acknowledgement spoken ahead of it.
    "VOICE_DEEP_ACK_SECONDS": "0",
}.items():
    if not os.environ.get(_key):
        os.environ[_key] = _value

from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pipecat.frames.frames import (  # noqa: E402
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor  # noqa: E402
from pipecat.services.tts_service import TTSService  # noqa: E402
from pipecat.utils.time import time_now_iso8601  # noqa: E402

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent  # noqa: E402
from tests.support.fake_supabase import FakeSupabase  # noqa: E402

ORG_ID = "00000000-0000-4000-8000-0000000000a1"
USER_ID = "00000000-0000-4000-8000-0000000000c3"
USER_UTTERANCE = "which account is our priority this quarter"
ASSISTANT_REPLY = "Acme is the priority account this quarter. Northwind comes next."
# 16 kHz mono int16: 32000 bytes per second of captured audio.
START_AFTER_BYTES = 8_000
FINAL_AFTER_BYTES = 24_000

DB = FakeSupabase()
STATE: dict[str, Any] = {"pcm_bytes_in": 0, "llm_queries": [], "durable_history_seen": []}


class ScriptedFluxSTT(FrameProcessor):
    """Emits Deepgram Flux's turn frames once enough real browser PCM has arrived."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bytes = 0
        self._phase = "idle"

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if not isinstance(frame, InputAudioRawFrame) or self._phase == "done":
            return
        self._bytes += len(frame.audio)
        STATE["pcm_bytes_in"] = self._bytes
        if self._phase == "idle" and self._bytes >= START_AFTER_BYTES:
            self._phase = "speaking"
            await self.broadcast_frame(ProposedUserStartedSpeakingFrame)
            await self.push_frame(
                InterimTranscriptionFrame(
                    text=USER_UTTERANCE.rsplit(" ", 2)[0], user_id=USER_ID, timestamp=time_now_iso8601()
                )
            )
        elif self._phase == "speaking" and self._bytes >= FINAL_AFTER_BYTES:
            self._phase = "done"
            await self.push_frame(
                TranscriptionFrame(USER_UTTERANCE, USER_ID, time_now_iso8601(), finalized=True)
            )
            await self.broadcast_frame(ProposedUserStoppedSpeakingFrame)


class ToneTTS(TTSService):
    """Synthesizes an audible 330 Hz tone, 40 ms per word."""

    def __init__(self, **kwargs: Any) -> None:
        from pipecat.services.settings import TTSSettings

        super().__init__(
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model=None, voice=None, language=None),
            **kwargs,
        )

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        rate = self.sample_rate or 24000
        samples = max(1, len(text.split())) * rate // 25
        pcm = b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * 330 * i / rate))) for i in range(samples)
        )
        await self.stop_ttfb_metrics()
        chunk = rate // 10 * 2
        for offset in range(0, len(pcm), chunk):
            yield TTSAudioRawFrame(pcm[offset : offset + chunk], rate, 1, context_id=context_id)


class ScriptedIntelligence:
    """Stands in for the reasoning model; records what the voice path sent it."""

    async def execute_task_streaming(self, **kwargs: Any):
        STATE["llm_queries"].append(kwargs.get("query"))
        STATE["durable_history_seen"].append(
            [m.get("content") for m in (kwargs.get("conversation_history") or [])]
        )
        for word in ASSISTANT_REPLY.split(" "):
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": word + " "})
        yield AssistantStreamComplete(
            full_content=ASSISTANT_REPLY,
            tool_results=[],
            react_result=None,
            model="harness",
            message_id=str(uuid.uuid4()),
        )


def _install_fakes() -> None:
    import app.operators.agent_intelligence as agent_intelligence
    import app.routers.assistant as assistant_router
    import app.workflows.repository as repository
    from app.services import chat_turn_cancel_service

    repository.get_supabase_client = lambda _settings=None: DB  # type: ignore[assignment]
    assistant_router.get_supabase_client = lambda _settings=None: DB  # type: ignore[assignment]
    assistant_router._remember_completed_turn = lambda **_kwargs: None  # type: ignore[assignment]
    chat_turn_cancel_service.get_redis_client = lambda _settings=None: None  # type: ignore[assignment]
    agent_intelligence.get_agent_intelligence = lambda: ScriptedIntelligence()  # type: ignore[assignment]


def _seed() -> str:
    conv = DB.seed_conversation(org_id=ORG_ID, user_id=USER_ID)
    DB.tables.setdefault("conversation_messages", []).extend(
        [
            {"id": "seed-u", "conversation_id": conv, "role": "user", "content": "Remember that Acme is the priority account.", "created_at": "2026-10-05T10:00:00Z"},
            {"id": "seed-a", "conversation_id": conv, "role": "assistant", "content": "Noted, Acme is the priority.", "created_at": "2026-10-05T10:00:01Z"},
        ]
    )
    return conv


def build_app() -> FastAPI:
    _install_fakes()
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/harness/state")
    async def state() -> dict[str, Any]:
        return {
            **STATE,
            "seeded_conversation_id": STATE.get("seeded_conversation_id"),
            "conversation_messages": [
                {k: row.get(k) for k in ("id", "conversation_id", "role", "content")}
                for row in DB.tables.get("conversation_messages", [])
            ],
        }

    @app.websocket("/api/voice/pipecat/ws")
    async def pipecat_ws(websocket: WebSocket) -> None:
        from pipecat.pipeline.runner import PipelineRunner

        from app.config import get_settings
        from app.services.pipecat_voice.pipeline import build_pipecat_voice_task
        from app.services.pipecat_voice.stt_factory import STT_FLUX

        await websocket.accept()
        # Each socket resumes its own freshly seeded conversation, so durable
        # history and persistence can be asserted per session.
        conversation_id = websocket.query_params.get("conversation_id") or _seed()
        STATE["seeded_conversation_id"] = conversation_id
        task, _meta = build_pipecat_voice_task(
            websocket=websocket,
            settings=get_settings(),
            org_id=ORG_ID,
            user_id=USER_ID,
            conversation_id=conversation_id,
            stt_service=ScriptedFluxSTT(),
            stt_service_info={"stt_provider_key": STT_FLUX, "stt_provider": "harness_scripted_flux"},
            tts_service=ToneTTS(sample_rate=24000),
        )
        await PipelineRunner(handle_sigint=False).run(task)

    return app


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()
    # The spec reads /harness/state before and after a turn on one pooled
    # connection. Uvicorn closes idle keep-alive sockets after 5 s, so a turn
    # that takes about 5 s races the close and the second read gets ECONNRESET.
    uvicorn.run(build_app(), host="127.0.0.1", port=args.port, log_level="info", timeout_keep_alive=120)


if __name__ == "__main__":
    main()
