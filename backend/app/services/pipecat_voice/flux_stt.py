"""Preserve Flux native turn detection while exposing its partial words.

Pipecat 1.12 sends Flux StartOfTurn/Update text to callbacks only. Gravitre's
backchannel strategy consumes InterimTranscriptionFrame, so without this bridge
an unambiguous stop waits for EndOfTurn. These ordered hooks emit interims only;
the SDK retains sole ownership of final transcription and turn commitment.
"""
from pipecat.frames.frames import InterimTranscriptionFrame
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.utils.time import time_now_iso8601


class InterimAwareFluxSTTService(DeepgramFluxSTTService):
    """Ordered adapter for the pinned SDK's native Flux protocol hooks."""

    partial_control_enabled = staticmethod(lambda: True)

    async def _push_partial(self, transcript: str) -> None:
        if (self._user_is_speaking and self.partial_control_enabled()
                and isinstance(transcript, str) and transcript.strip()):
            frame = InterimTranscriptionFrame(
                text=transcript, user_id="", timestamp=time_now_iso8601(),
            )
            # This bridge supplies overlap classification, not a new source
            # of speculative generation or retrieval during ordinary listening.
            frame.gravitre_turn_control_only = True
            await self.push_frame(frame)

    async def _handle_start_of_turn(self, transcript: str):
        await super()._handle_start_of_turn(transcript)
        await self._push_partial(transcript)

    async def _handle_update(self, transcript: str):
        await super()._handle_update(transcript)
        await self._push_partial(transcript)
