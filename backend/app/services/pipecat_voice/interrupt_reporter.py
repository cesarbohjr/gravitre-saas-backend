"""Track assistant text and report precise barge-in for ElevenLabs TTS.

Deepgram Speak v2 sendInterrupt/SpeakV2SpeechInterrupted applies only when TTS
is Deepgram Speak. Gravitre live TTS is ElevenLabs Flash over WebSocket, so we
emulate the useful contract: on InterruptionFrame, emit spoken_so_far vs
full_draft plus optional client playback_offset_ms.
"""
from __future__ import annotations

from typing import Any

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputTransportMessageUrgentFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.core.logging import get_logger

logger = get_logger(__name__)


class ElevenLabsInterruptReporter(FrameProcessor):
    """Accumulate draft/spoken text; on interrupt publish speech.interrupted."""

    def __init__(
        self,
        *,
        reconcile_played_audio_enabled: bool = False,
        settings: Any | None = None,
        org_id: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        spoken_ledger: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._draft = ""
        self._spoken_aligned = ""
        self._last_playback_offset_ms: float | None = None
        self._reconcile_enabled = bool(reconcile_played_audio_enabled)
        # Populated by SpokenTextTapProcessor downstream of transport.output();
        # this processor cannot see TTSTextFrame itself (it sits upstream of tts).
        self._spoken_ledger = spoken_ledger
        self._settings = settings
        self._org_id = org_id
        self._user_id = user_id
        self._conversation_id = conversation_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._draft = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            if self._spoken_ledger is not None:
                self._spoken_ledger.reset()
        elif isinstance(frame, LLMTextFrame):
            self._draft += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, OutputTransportMessageUrgentFrame):
            msg = frame.message if isinstance(frame.message, dict) else {}
            if str(msg.get("type") or "") == "assistant_text":
                self._draft += str(msg.get("delta") or "")
        elif isinstance(frame, TTSTextFrame):
            self._spoken_aligned += str(getattr(frame, "text", None) or "")
        elif isinstance(frame, LLMFullResponseEndFrame):
            pass
        elif isinstance(frame, InterruptionFrame):
            offset = getattr(frame, "gravitre_playback_offset_ms", None)
            if offset is not None:
                try:
                    self._last_playback_offset_ms = float(offset)
                except (TypeError, ValueError):
                    self._last_playback_offset_ms = None
            # Spoken-text signal, in order of fidelity:
            #   1. the downstream tap's ledger (real playback-ordered TTS text),
            #   2. TTSTextFrames seen directly (only possible if this processor is
            #      ever moved downstream of tts),
            #   3. the draft — which means "assume all of it was heard", i.e. no
            #      truncation. That is the safe degradation, never an empty string.
            # An empty ledger only counts as genuine silence once the tap has
            # proven it receives frames (`ever_recorded`); otherwise a routing
            # regression would truncate every turn to nothing.
            ledger_spoken: str | None = None
            if self._spoken_ledger is not None and self._spoken_ledger.ever_recorded:
                ledger_spoken = self._spoken_ledger.snapshot()
            spoken = (
                ledger_spoken
                if ledger_spoken is not None
                else (self._spoken_aligned or self._draft or "")
            ).strip()
            full = (self._draft or self._spoken_aligned or spoken).strip()
            payload = {
                "type": "speech.interrupted",
                "tts_provider": "elevenlabs",
                "speak_v2": False,
                "speak_v2_note": "N/A — live TTS is ElevenLabs, not Deepgram Speak v2",
                "spoken_text": spoken[:2000],
                "full_draft_text": full[:2000],
                "interrupted": True,
                "playback_offset_ms": self._last_playback_offset_ms,
            }
            # Phase 5 (conversational polish): tell the client which text was
            # actually heard so the next turn's history is not padded with a tail
            # the user never received. Flag-gated; off means legacy payload only.
            reconcile_meta: dict[str, Any] = {}
            if self._reconcile_enabled:
                from app.services.pipecat_voice.voice_conversational_polish import (
                    reconcile_played_audio,
                )

                reconciliation = reconcile_played_audio(
                    spoken_text=spoken,
                    full_draft_text=full,
                )
                reconcile_meta = reconciliation.as_meta()
                # Which signal produced `spoken` — the difference between a real
                # reconciliation and a safe degradation is otherwise invisible.
                reconcile_meta["spoken_source"] = (
                    "tap_ledger"
                    if ledger_spoken is not None
                    else ("tts_text_frames" if self._spoken_aligned else "draft_fallback")
                )
                payload["reconciled_text"] = reconciliation.reconciled_text[:2000]
                payload["reconcile_played_audio"] = True
                payload.update(reconcile_meta)
                if self._settings is not None and self._org_id:
                    from app.services.pipecat_voice.voice_latency_metrics import (
                        record_voice_barge_in_reconciliation,
                    )

                    record_voice_barge_in_reconciliation(
                        self._settings,
                        org_id=self._org_id,
                        user_id=self._user_id,
                        conversation_id=self._conversation_id,
                        reconcile_meta=reconcile_meta,
                        playback_offset_ms=self._last_playback_offset_ms,
                    )
            logger.info(
                "pipecat_speech_interrupted spoken_chars=%s draft_chars=%s offset_ms=%s reconcile=%s",
                len(spoken),
                len(full),
                self._last_playback_offset_ms,
                reconcile_meta or "off",
            )
            await self.push_frame(
                OutputTransportMessageUrgentFrame(message=payload),
                direction,
            )
            # Clear so a follow-up turn starts clean.
            self._draft = ""
            self._spoken_aligned = ""
            self._last_playback_offset_ms = None
            if self._spoken_ledger is not None:
                self._spoken_ledger.reset()

        await self.push_frame(frame, direction)
