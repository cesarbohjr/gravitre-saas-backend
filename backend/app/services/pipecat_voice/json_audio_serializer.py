"""Browser-friendly JSON audio serializer for FastAPIWebsocketTransport.

Binary protobuf is awkward for the existing duplex FE; we use text JSON frames:
  inbound:  {"type":"audio","pcm16_b64":"...","sample_rate":16000,"num_channels":1}
  inbound:  {"type":"interrupt"}
  inbound:  {"type":"text","text":"..."}   # smoke / text ingress without mic
  outbound: {"type":"audio","pcm16_b64":"...","sample_rate":16000,"num_channels":1}
  outbound: {"type":"event","event":"...","payload":{...}}
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
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer


class GravitreJsonAudioSerializer(FrameSerializer):
    async def setup(self, frame: StartFrame) -> None:
        pass

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, (OutputAudioRawFrame, TTSAudioRawFrame)):
            return json.dumps(
                {
                    "type": "audio",
                    "pcm16_b64": base64.b64encode(frame.audio).decode("ascii"),
                    "sample_rate": int(getattr(frame, "sample_rate", None) or 16000),
                    "num_channels": int(getattr(frame, "num_channels", None) or 1),
                }
            )
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
            return InputAudioRawFrame(
                audio=raw,
                sample_rate=int(msg.get("sample_rate") or 16000),
                num_channels=int(msg.get("num_channels") or 1),
            )
        if kind == "interrupt":
            return InterruptionFrame()
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
        if kind == "input_text":
            text = str(msg.get("text") or "").strip()
            if not text:
                return None
            return InputTextRawFrame(text=text)
        return None
