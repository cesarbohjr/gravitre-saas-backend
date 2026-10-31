"""Preserve Flux native turn detection while exposing its partial words.

Pipecat 1.12 sends Flux StartOfTurn/Update text to callbacks only. Gravitre's
backchannel strategy consumes InterimTranscriptionFrame, so without this bridge
an unambiguous stop waits for EndOfTurn. These ordered hooks emit interims only;
the SDK retains sole ownership of final transcription and turn commitment.
"""
from pipecat.frames.frames import InterimTranscriptionFrame, ProposedUserStartedSpeakingFrame
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.utils.time import time_now_iso8601

from app.services.pipecat_voice.backchannel_classifier import InterruptIntent, classify_interrupt_intent


class InterimAwareFluxSTTService(DeepgramFluxSTTService):
    """Ordered adapter for the pinned SDK's native Flux protocol hooks."""

    partial_control_enabled = staticmethod(lambda: True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._early_control_turn_index = None
        self._dispatch_turn_index = None
        self._committed_turn_index = -1

    async def _connect(self):
        # Flux turn indices are connection-scoped, including reconnects.
        self._early_control_turn_index = None
        self._dispatch_turn_index = None
        self._committed_turn_index = -1
        await super()._connect()

    async def _handle_turn_info(self, data):
        index = data.get('turn_index')
        self._dispatch_turn_index = index if type(index) is int and index >= 0 else None
        event, transcript = data.get('event'), data.get('transcript', '')
        if (event == 'Update' and not self._user_is_speaking
                and self.partial_control_enabled()
                and self._dispatch_turn_index is not None
                and index > self._committed_turn_index
                and isinstance(transcript, str) and transcript.strip()
                and classify_interrupt_intent(transcript) is InterruptIntent.TASK_CANCEL):
            # Measured Flux Updates can contain a clear cancel before native
            # StartOfTurn. Propose only that explicit intent to the existing
            # echo/origin/backchannel/turn authority. This never commits text,
            # approves work, starts inference, or treats bare "stop" as cancel.
            if self._early_control_turn_index != index:
                self._early_control_turn_index = index
                await self.broadcast_frame(ProposedUserStartedSpeakingFrame)
            await self._push_partial(transcript, before_native_start=True)
        await super()._handle_turn_info(data)
        if event == 'EndOfTurn':
            if self._dispatch_turn_index is not None:
                self._committed_turn_index = max(self._committed_turn_index, index)
            self._early_control_turn_index = None

    async def _push_partial(self, transcript: str, *, before_native_start=False) -> None:
        if ((self._user_is_speaking or before_native_start) and self.partial_control_enabled()
                and isinstance(transcript, str) and transcript.strip()):
            frame = InterimTranscriptionFrame(
                text=transcript, user_id="", timestamp=time_now_iso8601(),
            )
            # This bridge supplies overlap classification, not a new source
            # of speculative generation or retrieval during ordinary listening.
            frame.gravitre_turn_control_only = True
            await self.push_frame(frame)

    async def _handle_start_of_turn(self, transcript: str):
        if (self._dispatch_turn_index is not None
                and self._early_control_turn_index == self._dispatch_turn_index):
            # Preserve the pinned SDK's speaking state and callback, without a
            # second start proposal for the same provider turn. Its EOT/final
            # transcription path remains entirely SDK-owned.
            self._user_is_speaking = True
            await self._call_event_handler('on_start_of_turn', transcript)
        else:
            await super()._handle_start_of_turn(transcript)
        await self._push_partial(transcript)

    async def _handle_update(self, transcript: str):
        await super()._handle_update(transcript)
        await self._push_partial(transcript)
