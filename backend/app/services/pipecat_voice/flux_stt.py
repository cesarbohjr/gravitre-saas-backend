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

    async def _push_partial(self, transcript: str) -> None:
        if self._user_is_speaking and isinstance(transcript, str) and transcript.strip():
            await self.push_frame(InterimTranscriptionFrame(
                text=transcript, user_id="", timestamp=time_now_iso8601(),
            ))

    async def _handle_start_of_turn(self, transcript: str):
        await super()._handle_start_of_turn(transcript)
        await self._push_partial(transcript)

    async def _handle_update(self, transcript: str):
        await super()._handle_update(transcript)
        await self._push_partial(transcript)
