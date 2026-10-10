"""Browser-friendly JSON audio serializer for FastAPIWebsocketTransport.

Binary protobuf is awkward for the existing duplex FE; we use text JSON frames:
  inbound:  {"type":"audio","pcm16_b64":"...","sample_rate":16000,"num_channels":1}
  inbound:  {"type":"interrupt"}
  inbound:  {"type":"text","text":"..."}   # smoke / text ingress without mic
  inbound:  {"type":"playback.started","receive_to_playback_ms":120}  # latency evidence only
  outbound: {"type":"audio","pcm16_b64":"...","sample_rate":16000,"num_channels":1}
  outbound: {"type":"event","event":"...","payload":{...}}

Reply identity of outbound audio
--------------------------------
The output transport re-chunks audio and rebuilds every frame before it is
serialized, so nothing attached to a TTS frame reaches ``serialize``. What
does survive is order: a non-urgent ``OutputTransportMessageFrame`` waits in
the transport's audio queue behind the audio pushed before it.
``ReplyAudioStampProcessor`` (between TTS and transport.output) binds each TTS
context to the reply that generated it and drops a reply mark into that queue
whenever the audio's reply changes; the serializer stamps audio from the last
mark it saw. A late frame of a cancelled reply therefore carries its own (old)
id, and the stamp processor drops it before it is queued at all.
"""
from __future__ import annotations

import base64
import json
from typing import Any

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InputTextRawFrame,
    InterruptionFrame,
    InterimTranscriptionFrame,
    LLMFullResponseStartFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.serializers.base_serializer import FrameSerializer

from app.core.logging import get_logger

logger = get_logger(__name__)

# In-band, server-internal: never sent to the browser.
REPLY_AUDIO_MARK = "gravitre.reply_audio_mark"
# Attribute the cognitive bridge sets on its LLMFullResponseStartFrame.
REPLY_ID_ATTR = "gravitre_reply_id"


def reply_audio_mark(reply_id: int) -> OutputTransportMessageFrame:
    return OutputTransportMessageFrame(message={"type": REPLY_AUDIO_MARK, "reply_id": int(reply_id)})


class ReplyAudioStampProcessor(FrameProcessor):
    """Bind outbound audio to the reply that generated it; drop cancelled replies' audio.

    Sits between the TTS service and ``transport.output()``. The TTS emits a
    reply's ``LLMFullResponseStartFrame`` only after the previous reply's
    audio has drained, so every TTS context first seen after that frame
    belongs to that reply. The binding is made once, when the audio is
    generated; ``reply_id`` advancing later never re-labels it.
    """

    def __init__(self, *, voice_session: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._session = voice_session
        # Reply whose LLM response most recently opened at the TTS output.
        self._generation_reply_id: int | None = None
        # Reply id of the last mark queued to the transport (None: re-mark).
        self._marked_reply_id: int | None = None
        self.dropped_frames = 0

    def _current_generation(self) -> int:
        if self._generation_reply_id is not None:
            return self._generation_reply_id
        reply_id = getattr(self._session, "reply_id", 0)
        return reply_id if isinstance(reply_id, int) else 0

    def _reply_for(self, frame: Frame) -> int:
        context_id = getattr(frame, "context_id", None)
        generation = self._current_generation()
        binder = getattr(self._session, "bind_audio_context", None)
        if context_id and callable(binder):
            return int(binder(str(context_id), generation))
        return generation

    def _suppressed(self, reply_id: int) -> bool:
        probe = getattr(self._session, "reply_audio_suppressed", None)
        return bool(callable(probe) and probe(reply_id))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, InterruptionFrame):
            # The transport clears its audio queue (marks included): the next
            # audio must carry a fresh mark.
            self._marked_reply_id = None
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, LLMFullResponseStartFrame):
            reply_id = getattr(frame, REPLY_ID_ATTR, None)
            if not isinstance(reply_id, int):
                reply_id = getattr(self._session, "reply_id", 0)
            self._generation_reply_id = int(reply_id) if isinstance(reply_id, int) else 0
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, (TTSStartedFrame, TTSTextFrame)):
            # Bind the context as early as the TTS names it.
            self._reply_for(frame)
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, OutputAudioRawFrame):
            reply_id = self._reply_for(frame)
            if self._suppressed(reply_id):
                self.dropped_frames += 1
                if self.dropped_frames == 1 or self.dropped_frames % 50 == 0:
                    logger.info(
                        "pipecat_cancelled_reply_audio_dropped reply_id=%s dropped=%s",
                        reply_id,
                        self.dropped_frames,
                    )
                return
            setattr(frame, REPLY_ID_ATTR, reply_id)
            if reply_id != self._marked_reply_id:
                self._marked_reply_id = reply_id
                await self.push_frame(reply_audio_mark(reply_id), direction)
            await self.push_frame(frame, direction)
            return
        await self.push_frame(frame, direction)


class GravitreJsonAudioSerializer(FrameSerializer):
    def __init__(
        self,
        *,
        default_origin: str = "user_mic",
        session: Any | None = None,
        turn_trace: Any | None = None,
    ) -> None:
        self._default_origin = default_origin
        self._session_origin: str | None = None
        self._voice_session = session
        self._turn_trace = turn_trace
        # Reply id from the last in-band mark; None until the stamp processor
        # is seen (then stamping falls back to the session's current reply).
        self._audio_reply_id: int | None = None
        self._marks_seen = False

    async def setup(self, frame: StartFrame) -> None:
        pass

    def _audio_reply_stamp(self) -> int | None:
        if self._audio_reply_id is not None:
            return self._audio_reply_id
        session = self._voice_session
        if self._marks_seen:
            # Marked stream, but the mark was cleared by an interruption and no
            # new one arrived: only a stale frame can get here. Label it as the
            # cut-off reply so the browser drops it, never as the new one.
            through = getattr(session, "cancelled_through_reply_id", None)
            if isinstance(through, int) and through >= 0:
                return through
        reply_id = getattr(session, "reply_id", None)
        return reply_id if isinstance(reply_id, int) else None

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputTransportMessageFrame) and not isinstance(
            frame, OutputTransportMessageUrgentFrame
        ):
            msg = frame.message if isinstance(frame.message, dict) else {}
            if msg.get("type") == REPLY_AUDIO_MARK:
                reply_id = msg.get("reply_id")
                self._audio_reply_id = int(reply_id) if isinstance(reply_id, int) else None
                self._marks_seen = True
                return None
        if isinstance(frame, InterruptionFrame):
            self._audio_reply_id = None
            return None
        if isinstance(frame, (OutputAudioRawFrame, TTSAudioRawFrame)):
            payload: dict[str, Any] = {
                "type": "audio",
                "pcm16_b64": base64.b64encode(frame.audio).decode("ascii"),
                "sample_rate": int(getattr(frame, "sample_rate", None) or 16000),
                "num_channels": int(getattr(frame, "num_channels", None) or 1),
            }
            reply_id = self._audio_reply_stamp()
            if isinstance(reply_id, int):
                payload["reply_id"] = reply_id
            return json.dumps(payload)
        if isinstance(frame, InterimTranscriptionFrame):
            return json.dumps(
                {
                    "type": "transcript",
                    "text": frame.text,
                    "final": False,
                    "user_id": getattr(frame, "user_id", "") or "",
                }
            )
        if isinstance(frame, TranscriptionFrame):
            return json.dumps(
                {
                    "type": "transcript",
                    "text": frame.text,
                    "final": True,
                    "user_id": getattr(frame, "user_id", "") or "",
                }
            )
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            msg = frame.message if isinstance(frame.message, dict) else {"payload": frame.message}
            return json.dumps(msg)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                # Treat raw binary as PCM16 mono @ 16k (fallback for harnesses).
                return InputAudioRawFrame(audio=data, sample_rate=16000, num_channels=1)
        try:
            msg: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError:
            return None
        kind = str(msg.get("type") or "").strip().lower()
        if kind == "audio":
            raw = base64.b64decode(str(msg.get("pcm16_b64") or ""))
            if not raw:
                return None
            from app.services.pipecat_voice.voice_audio_origin import normalize_origin

            origin = normalize_origin(
                msg.get("audio_origin") or msg.get("origin") or self._session_origin,
                default=self._default_origin,
            )
            self._session_origin = origin
            from app.services.pipecat_voice.voice_audio_origin import set_session_origin

            set_session_origin(origin)
            if self._voice_session is not None:
                self._voice_session.set_origin(origin)
            frame = InputAudioRawFrame(
                audio=raw,
                sample_rate=int(msg.get("sample_rate") or 16000),
                num_channels=int(msg.get("num_channels") or 1),
            )
            setattr(frame, "gravitre_audio_origin", origin)
            return frame
        if kind == "interrupt":
            frame = InterruptionFrame()
            origin = self._session_origin or self._default_origin
            if self._voice_session is not None:
                origin = self._voice_session.origin
            setattr(frame, "gravitre_audio_origin", origin)
            # Optional FE playback cursor — Speak-v2-style offset for ElevenLabs path.
            offset = msg.get("playback_offset_ms")
            if offset is not None:
                try:
                    setattr(frame, "gravitre_playback_offset_ms", float(offset))
                except (TypeError, ValueError):
                    pass
            return frame
        if kind == "text":
            text = str(msg.get("text") or "").strip()
            if not text:
                return None
            # Text ingress for smokes / hybrid FE that still uses client Deepgram.
            # finalized=True so the user aggregator emits LLMContext without waiting on VAD.
            return TranscriptionFrame(
                text=text,
                user_id=str(msg.get("user_id") or "browser"),
                timestamp=str(msg.get("timestamp") or ""),
                finalized=True,
            )
        if kind == "playback.started":
            # Browser: first audio of the reply received -> audible playback
            # scheduled, on the browser's own clock. Recorded on the turn's
            # latency trace; never becomes a pipeline frame.
            if self._turn_trace is not None:
                self._turn_trace.on_client_playback_started(msg.get("receive_to_playback_ms"))
            return None
        if kind == "input_text":
            text = str(msg.get("text") or "").strip()
            if not text:
                return None
            return InputTextRawFrame(text=text)
        return None
