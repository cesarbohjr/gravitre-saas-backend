"""Scripted stand-ins for everything outside the Gravitre voice pipeline.

Only the providers and the client are replaced; every processor between the
socket and the providers is the production one (``build_pipecat_voice_task``).

- ``FakeClientWebSocket``: the browser end of the socket. Records every message
  with its virtual arrival time and feeds audio to ``BrowserPlaybackModel``.
- ``ScriptedFluxSTT``: emits the frames Pipecat 1.12's Deepgram Flux service
  emits (ProposedUserStarted/Stopped, EagerTranscription, EagerEndOfTurnCancel,
  finalized Transcription). Flux 1.12 pushes NO InterimTranscriptionFrame
  (``_handle_update`` only fires an event handler), so interims are off by
  default; ``emit_interims=True`` models a hypothetical STT that does.
- ``FakeStreamingTTS``: an ElevenLabs-websocket-shaped TTS. One audio context
  per reply, a provider task that answers after a first-byte delay and streams
  PCM faster than real time with word timestamps, honours flush/close, and can
  keep emitting for ``late_audio_s`` after a context is closed (stale provider
  frames). Every PCM sample of a segment carries the segment id, so the client
  can label any frame (filler / progress / answer) even after re-chunking.
- ``ScriptedBrain``: ``execute_task_streaming`` driven by a per-scenario plan
  (first-token delay, streamed text, tool calls with delay/failure, governed
  writes checked against the real barge-in write gate).
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import re
import struct
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable

from pipecat.frames.frames import (
    EagerEndOfTurnCancelFrame,
    EagerTranscriptionFrame,
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.tts_service import TTSService
from pipecat.utils.time import time_now_iso8601
from starlette.websockets import WebSocketState

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from tests.support.fake_supabase import FakeQuery, FakeSupabase

SAMPLE_RATE = 24000
# Set inside a speculative run's task so the brain knows which run called it.
SPEC_RUN: contextvars.ContextVar[Any] = contextvars.ContextVar("bench_spec_run", default=None)


def norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower().replace("’", "'"))


# ---------------------------------------------------------------------------
# Run-wide event log


@dataclass
class Segment:
    seg_id: int
    label: str  # filler | progress | answer
    text: str
    reply_truth: int  # VoicePipelineSession.reply_id when the text reached the TTS
    context_id: str
    requested_at: float
    words: int
    audio_s: float = 0.0


@dataclass
class BrainCall:
    call_id: int
    query: str
    speculative: bool
    started_at: float
    history: list[dict[str, Any]]
    spec_run: Any = None
    ended_at: float | None = None
    completed: bool = False
    cancelled: bool = False
    first_text_at: float | None = None
    full_content: str = ""


class Recorder:
    """Everything observable in one run, stamped with virtual time."""

    def __init__(self, clock: Any) -> None:
        self.clock = clock
        self.events: list[tuple[float, str, dict[str, Any]]] = []
        self.segments: dict[int, Segment] = {}
        self._next_seg = 1
        self.brain_calls: list[BrainCall] = []
        self.writes: list[dict[str, Any]] = []
        self.narrations: dict[tuple[str, ...], str] = {}
        self.spec_runs: list[dict[str, Any]] = []
        self.provider_chunks_after_close = 0
        self.provider_chunks_after_close_accepted = 0
        self.voice_session: Any = None

    def now(self) -> float:
        return self.clock.now

    def log(self, kind: str, **data: Any) -> None:
        self.events.append((self.clock.now, kind, data))

    def register_narration(self, text: str | None, label: str) -> None:
        if text:
            self.narrations[tuple(norm_words(text))] = label

    def label_for(self, text: str) -> str:
        key = tuple(norm_words(text))
        if key in self.narrations:
            return self.narrations[key]
        for nkey, label in self.narrations.items():
            if nkey and len(key) >= len(nkey) and key[: len(nkey)] == nkey and len(key) - len(nkey) <= 1:
                return label
        return "answer"

    def new_segment(self, *, text: str, context_id: str) -> Segment:
        seg_id = self._next_seg
        self._next_seg = 1 if self._next_seg >= 32000 else self._next_seg + 1
        reply = int(getattr(self.voice_session, "reply_id", 0) or 0)
        seg = Segment(
            seg_id=seg_id,
            label=self.label_for(text),
            text=text,
            reply_truth=reply,
            context_id=context_id,
            requested_at=self.clock.now,
            words=len(norm_words(text)) or 1,
        )
        self.segments[seg_id] = seg
        self.log("tts_request", seg_id=seg_id, label=seg.label, text=text, reply_truth=reply)
        return seg


# ---------------------------------------------------------------------------
# Supabase


class BenchQuery(FakeQuery):
    """FakeQuery plus the filters the voice persistence path also uses."""

    def __init__(self, client: "FakeSupabase", table: str) -> None:
        super().__init__(client, table)
        self._gt: list[tuple[str, Any]] = []

    def gt(self, column: str, value: Any) -> "BenchQuery":
        self._gt.append((column, value))
        return self

    def _matches(self, row: dict[str, Any]) -> bool:
        if not super()._matches(row):
            return False
        for col, val in self._gt:
            if str(row.get(col) or "") <= str(val or ""):
                return False
        return True

    def __getattr__(self, name: str) -> Any:
        # Unmodelled filter/modifier (neq, in_, is_, maybe_single, ...): keep chaining.
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *_a, **_k: self


class BenchSupabase(FakeSupabase):
    def __init__(self, clock: Any) -> None:
        super().__init__()
        self._clock = clock
        self._seq = 0

    def table(self, name: str) -> BenchQuery:
        return BenchQuery(self, name)

    def stamp(self) -> str:
        # Monotonic created_at so ordering by created_at is stable.
        self._seq += 1
        return f"2026-10-10T10:{int(self._clock.now) // 60:02d}:{int(self._clock.now) % 60:02d}.{self._seq:06d}Z"


def install_created_at_hook(db: BenchSupabase) -> None:
    def _hook(query: FakeQuery) -> None:
        if query.op == "insert" and query.table == "conversation_messages":
            batch = query.payload if isinstance(query.payload, list) else [query.payload]
            for row in batch:
                if isinstance(row, dict):
                    row.setdefault("created_at", db.stamp())

    db.hooks.append(_hook)


# ---------------------------------------------------------------------------
# Browser end of the socket


class BrowserPlaybackModel:
    """Models ``use-voice-duplex-session.ts`` + ``voice-pcm-jitter.ts`` playback.

    - Audio with ``reply_id <= interruptedReplyId`` is dropped on arrival.
    - ``speech.interrupted`` raises the cut to its reply_id and flushes queued
      playback (the chunk playing is cut at that instant).
    - A chunk is scheduled back-to-back with the previous one; when the queue
      has run dry it starts ``lead_s`` from now, and a mid-reply underrun grows
      the lead by 60 ms up to 320 ms (the jitter buffer's real constants).
    - ``network_s`` is a fixed one-way delay applied to every message (0 by
      default: the network is not modelled).
    """

    def __init__(self, recorder: Recorder, *, initial_lead_s: float = 0.12, network_s: float = 0.0) -> None:
        self.rec = recorder
        self.lead_s = initial_lead_s
        self.max_lead_s = 0.32
        self.lead_step_s = 0.06
        self.network_s = network_s
        self.next_time = 0.0
        self.last_chunk_at: float | None = None
        self.cut: int | None = None
        # Each chunk: dict(seg, reply_stamp, reply_truth, label, recv, start, end, played_end)
        self.chunks: list[dict[str, Any]] = []
        self.dropped: list[dict[str, Any]] = []
        self.messages: list[tuple[float, dict[str, Any]]] = []
        self.interrupts: list[tuple[float, dict[str, Any]]] = []

    def _now(self) -> float:
        return self.rec.now() + self.network_s

    def on_message(self, msg: dict[str, Any]) -> None:
        now = self._now()
        kind = str(msg.get("type") or "")
        if kind != "audio":
            self.messages.append((now, msg))
        if kind == "speech.interrupted":
            rid = msg.get("reply_id")
            if isinstance(rid, int):
                self.cut = max(self.cut if self.cut is not None else -1, rid)
            self.interrupts.append((now, msg))
            self._flush(now)
            return
        if kind != "audio":
            return
        import base64

        pcm = base64.b64decode(str(msg.get("pcm16_b64") or ""))
        if len(pcm) < 2:
            return
        seg_id = struct.unpack_from("<h", pcm, 0)[0]
        seg = self.rec.segments.get(seg_id)
        rid = msg.get("reply_id")
        entry = {
            "seg": seg_id,
            "label": seg.label if seg else "unknown",
            "reply_truth": seg.reply_truth if seg else None,
            "reply_stamp": rid,
            "recv": now,
            "dur": len(pcm) / 2 / int(msg.get("sample_rate") or SAMPLE_RATE),
        }
        if isinstance(rid, int) and self.cut is not None and rid <= self.cut:
            self.dropped.append(entry)
            return
        same_reply = self.last_chunk_at is not None and now - self.last_chunk_at <= 0.4
        self.last_chunk_at = now
        if self.next_time > now + 0.005:
            start = self.next_time
        else:
            if same_reply and self.next_time > 0:
                self.lead_s = min(self.max_lead_s, self.lead_s + self.lead_step_s)
            start = now + self.lead_s
        entry["start"] = start
        entry["end"] = start + entry["dur"]
        entry["played_end"] = entry["end"]
        self.next_time = entry["end"]
        self.chunks.append(entry)

    def _flush(self, now: float) -> None:
        for c in self.chunks:
            if c["start"] >= now:
                c["played_end"] = c["start"]  # never played
            elif c["end"] > now:
                c["played_end"] = now
        self.next_time = 0.0

    def played(self) -> list[dict[str, Any]]:
        return [c for c in self.chunks if c["played_end"] > c["start"]]


class FakeClientWebSocket:
    """Just enough of starlette's WebSocket for FastAPIWebsocketTransport."""

    def __init__(self, recorder: Recorder, browser: BrowserPlaybackModel, *, query: dict[str, str] | None = None) -> None:
        self.rec = recorder
        self.browser = browser
        self.client_state = WebSocketState.CONNECTED
        self.application_state = WebSocketState.CONNECTED
        self.query_params = dict(query or {})
        self.headers: dict[str, str] = {}
        self._inbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.ready = asyncio.Event()
        self.sent: list[tuple[float, dict[str, Any]]] = []

    async def receive(self) -> dict[str, Any]:
        return await self._inbound.get()

    def client_send(self, msg: dict[str, Any]) -> None:
        """Browser -> server message (e.g. {"type": "interrupt"})."""
        self._inbound.put_nowait({"type": "websocket.receive", "text": json.dumps(msg)})

    async def _deliver(self, data: str) -> None:
        if self.client_state != WebSocketState.CONNECTED:
            return
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            return
        if not isinstance(msg, dict):
            return
        if msg.get("type") == "session.ready":
            self.ready.set()
        if msg.get("type") == "audio":
            self.sent.append((self.rec.now(), {"type": "audio", "reply_id": msg.get("reply_id")}))
        else:
            self.sent.append((self.rec.now(), msg))
        self.browser.on_message(msg)

    async def send_text(self, data: str) -> None:
        await self._deliver(data)

    async def send_bytes(self, data: bytes) -> None:
        return None

    async def send_json(self, data: Any, mode: str = "text") -> None:
        await self._deliver(json.dumps(data))

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.drop()

    def drop(self) -> None:
        """The socket goes away (network drop or tab close)."""
        if self.client_state == WebSocketState.DISCONNECTED:
            return
        self.client_state = WebSocketState.DISCONNECTED
        self.application_state = WebSocketState.DISCONNECTED
        self._inbound.put_nowait({"type": "websocket.disconnect", "code": 1006})


# ---------------------------------------------------------------------------
# STT


class ScriptedFluxSTT(FrameProcessor):
    """Deepgram Flux's frame vocabulary, driven by the scenario timeline."""

    def __init__(self, *, recorder: Recorder, emit_interims: bool = False, eager_enabled: bool = True, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.rec = recorder
        self.emit_interims = emit_interims
        self.eager_enabled = eager_enabled
        self._eager_pending = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

    async def start_of_turn(self) -> None:
        self.rec.log("stt_start_of_turn")
        await self.broadcast_frame(ProposedUserStartedSpeakingFrame)

    async def update(self, text: str) -> None:
        if self.emit_interims and text:
            await self.push_frame(InterimTranscriptionFrame(text=text, user_id="bench-user", timestamp=time_now_iso8601()))

    async def eager_end_of_turn(self, text: str) -> None:
        if not self.eager_enabled:
            return
        self._eager_pending = True
        self.rec.log("stt_eager_eot", text=text)
        await self.push_frame(EagerTranscriptionFrame(text, "bench-user", time_now_iso8601()))

    async def turn_resumed(self) -> None:
        if self._eager_pending:
            self._eager_pending = False
            self.rec.log("stt_turn_resumed")
            await self.push_frame(EagerEndOfTurnCancelFrame())

    async def end_of_turn(self, text: str, *, confidence: float = 0.95) -> None:
        self._eager_pending = False
        self.rec.log("stt_end_of_turn", text=text)
        words = [{"word": w, "confidence": confidence} for w in text.split()]
        await self.push_frame(
            TranscriptionFrame(text, "bench-user", time_now_iso8601(), result={"words": words}, finalized=True)
        )
        await self.broadcast_frame(ProposedUserStoppedSpeakingFrame)


# ---------------------------------------------------------------------------
# TTS


@dataclass
class TTSConditions:
    first_byte_s: float = 0.25
    inter_sentence_s: float = 0.03
    word_audio_s: float = 0.32
    generation_speed: float = 3.0  # audio seconds produced per wall second
    late_audio_s: float = 0.0  # provider keeps sending this long after close


class _ProviderContext:
    def __init__(self, context_id: str) -> None:
        self.context_id = context_id
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.closed_at: float | None = None
        self.task: asyncio.Task[None] | None = None
        self.cum_s = 0.0


_FLUSH = object()


class FakeStreamingTTS(TTSService):
    def __init__(self, *, recorder: Recorder, conditions: TTSConditions, rng: Any, **kwargs: Any) -> None:
        from pipecat.services.settings import TTSSettings

        super().__init__(
            push_text_frames=False,
            push_stop_frames=False,
            pause_frame_processing=True,
            sample_rate=SAMPLE_RATE,
            settings=TTSSettings(model=None, voice=None, language=None),
            **kwargs,
        )
        self.rec = recorder
        self.cond = conditions
        self.rng = rng
        self._providers: dict[str, _ProviderContext] = {}

    def _jit(self, base: float, frac: float = 0.3) -> float:
        return max(0.0, base * (1.0 + self.rng.uniform(-frac, frac)))

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        if not self.audio_context_available(context_id):
            await self.create_audio_context(context_id)
            await self.start_ttfb_metrics()
            yield TTSStartedFrame(context_id=context_id)
        prov = self._providers.get(context_id)
        if prov is None or prov.closed_at is not None:
            prov = _ProviderContext(context_id)
            self._providers[context_id] = prov
            prov.task = asyncio.get_running_loop().create_task(self._provider_loop(prov))
        seg = self.rec.new_segment(text=text, context_id=context_id)
        prov.queue.put_nowait((text, seg))
        yield None

    async def flush_audio(self, context_id: str | None = None) -> None:
        cid = context_id or self.get_active_audio_context_id()
        prov = self._providers.get(cid or "")
        if prov is not None:
            prov.queue.put_nowait(_FLUSH)

    async def on_audio_context_interrupted(self, context_id: str) -> None:
        prov = self._providers.get(context_id)
        if prov is not None and prov.closed_at is None:
            prov.closed_at = self.rec.now()
            self.rec.log("tts_context_closed", context_id=context_id)
            if self.cond.late_audio_s <= 0 and prov.task is not None:
                prov.task.cancel()
        await super().on_audio_context_interrupted(context_id)

    async def _append(self, prov: _ProviderContext, frame: Any) -> None:
        if prov.closed_at is not None:
            self.rec.provider_chunks_after_close += 1
            if self.audio_context_available(prov.context_id):
                self.rec.provider_chunks_after_close_accepted += 1
        await self.append_to_audio_context(prov.context_id, frame)

    async def _provider_loop(self, prov: _ProviderContext) -> None:
        first = True
        try:
            while True:
                item = await prov.queue.get()
                if item is _FLUSH:
                    if prov.closed_at is None and self.audio_context_available(prov.context_id):
                        await self.append_to_audio_context(prov.context_id, TTSStoppedFrame(context_id=prov.context_id))
                        await self.remove_audio_context(prov.context_id)
                    return
                text, seg = item
                await asyncio.sleep(self._jit(self.cond.first_byte_s) if first else self.cond.inter_sentence_s)
                first = False
                words = text.split() or [text]
                for word in words:
                    if prov.closed_at is not None and self.rec.now() - prov.closed_at >= self.cond.late_audio_s:
                        return
                    dur = self.cond.word_audio_s
                    n = max(2, int(dur * SAMPLE_RATE))
                    pcm = struct.pack("<h", seg.seg_id) * n
                    seg.audio_s += dur
                    if prov.closed_at is None and self.audio_context_available(prov.context_id):
                        await self.add_word_timestamps([(word, prov.cum_s)], prov.context_id)
                    await self._append(prov, TTSAudioRawFrame(pcm, SAMPLE_RATE, 1, context_id=prov.context_id))
                    prov.cum_s += dur
                    await asyncio.sleep(dur / max(0.1, self.cond.generation_speed))
        except asyncio.CancelledError:
            return


# ---------------------------------------------------------------------------
# Brain


@dataclass
class Think:
    seconds: float


@dataclass
class Say:
    text: str
    token_s: float = 0.035


@dataclass
class Tool:
    name: str
    seconds: float
    fail: bool = False
    output: dict[str, Any] | None = None
    write_action: str | None = None  # governed write: checked against the barge-in gate
    pre_commit_s: float = 0.4  # time inside the tool before the provider call is made


Plan = list[Any]
Planner = Callable[[str, list[dict[str, Any]], Any], Plan]


class ScriptedBrain:
    """``execute_task_streaming`` that plays a scenario plan and records everything."""

    def __init__(self, recorder: Recorder, planner: Planner, ctx: Any, *, settings: Any, org_id: str) -> None:
        self.rec = recorder
        self.planner = planner
        self.ctx = ctx
        self.settings = settings
        self.org_id = org_id

    async def execute_task_streaming(self, **kwargs: Any) -> AsyncGenerator[Any, None]:
        query = str(kwargs.get("query") or "")
        history = [
            {"role": m.get("role"), "content": m.get("content")}
            for m in (kwargs.get("conversation_history") or [])
        ]
        spec_run = SPEC_RUN.get()
        call = BrainCall(
            call_id=len(self.rec.brain_calls) + 1,
            query=query,
            speculative=spec_run is not None,
            started_at=self.rec.now(),
            history=history,
            spec_run=spec_run,
        )
        if spec_run is not None:
            spec_run["call"] = call
        self.rec.brain_calls.append(call)
        self.rec.log("brain_start", call_id=call.call_id, query=query, speculative=call.speculative)
        conversation_id = kwargs.get("conversation_id")
        text_parts: list[str] = []
        tool_results: list[dict[str, Any]] = []
        try:
            for step in self.planner(query, history, self.ctx):
                if isinstance(step, Think):
                    await asyncio.sleep(step.seconds)
                elif isinstance(step, Say):
                    for i, word in enumerate(step.text.split(" ")):
                        if call.first_text_at is None:
                            call.first_text_at = self.rec.now()
                        delta = word if i == 0 and not text_parts else " " + word
                        text_parts.append(delta)
                        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": delta})
                        await asyncio.sleep(step.token_s)
                elif isinstance(step, Tool):
                    call_id = f"call-{uuid.uuid4().hex[:8]}"
                    yield AssistantStreamEvent(
                        sse_type="tool-input-available",
                        payload={"toolCallId": call_id, "toolName": step.name, "input": {}},
                    )
                    output: dict[str, Any]
                    if step.write_action:
                        await asyncio.sleep(min(step.pre_commit_s, step.seconds))
                        blocked = self._write_blocked(step.write_action, conversation_id)
                        record = {
                            "t": self.rec.now(),
                            "action": step.write_action,
                            "query": query,
                            "speculative": call.speculative,
                            "committed": not blocked,
                        }
                        self.rec.writes.append(record)
                        self.rec.log("write_commit" if not blocked else "write_blocked", **record)
                        await asyncio.sleep(max(0.0, step.seconds - step.pre_commit_s))
                        output = (
                            {"success": False, "error": "Stopped before sending. The write was not executed."}
                            if blocked
                            else {"success": True}
                        )
                    else:
                        await asyncio.sleep(step.seconds)
                        output = step.output or ({"success": False, "error": "The analytics service timed out."} if step.fail else {"results": [{}, {}, {}]})
                    tool_results.append({"tool": step.name, "output": output})
                    yield AssistantStreamEvent(
                        sse_type="tool-output-available",
                        payload={"toolCallId": call_id, "output": output},
                    )
            call.full_content = "".join(text_parts).strip()
            call.completed = True
            yield AssistantStreamComplete(
                full_content=call.full_content,
                tool_results=tool_results,
                react_result=None,
                model="bench",
                message_id=str(uuid.uuid4()),
            )
        except (asyncio.CancelledError, GeneratorExit):
            call.cancelled = True
            raise
        finally:
            call.ended_at = self.rec.now()
            self.rec.log(
                "brain_end",
                call_id=call.call_id,
                completed=call.completed,
                cancelled=call.cancelled,
            )

    def _write_blocked(self, action: str, conversation_id: Any) -> bool:
        """The production last-line write gate (``raise_if_barge_in_blocks_invoke``)."""
        from types import SimpleNamespace

        from app.services.tool_types import ToolValidationError
        from app.services.voice_barge_in_write import raise_if_barge_in_blocks_invoke

        ctx = SimpleNamespace(org_id=self.org_id, conversation_id=conversation_id, settings=self.settings)
        try:
            raise_if_barge_in_blocks_invoke(ctx, action)
        except ToolValidationError:
            return True
        return False
