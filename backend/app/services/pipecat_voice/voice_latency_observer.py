"""Phase 6 (conversational-realism): live per-stage voice latency observer.

Pipecat ships ``UserBotLatencyObserver`` (measures user-stopped-speaking to
bot-started-speaking, plus a per-service TTFB/text-aggregation breakdown when
``enable_metrics=True``). Real, live-code finding: that observer only starts
its clock on ``VADUserStoppedSpeakingFrame`` — a frame Silero VAD emits. Our
live path uses Deepgram Flux's native end-of-turn detection with NO VAD
stacked (see ``pipeline.py``), so Flux never emits that frame, and the stock
observer's clock would never start on live traffic: ``on_latency_measured``/
``on_latency_breakdown`` would silently never fire for the path that actually
serves gravitre.app today.

This subclass fixes that gap the same way ``BackchannelAwareUserTurnStartStrategy``
(Phase 1) works with Flux: it also starts the clock on
``ProposedUserStoppedSpeakingFrame`` — the real, earliest signal that the
user's audio ended, emitted by Flux itself — while leaving every other stock
behavior (TTFB accumulation, text-aggregation, function-call metrics,
first-bot-speech measurement) untouched.
"""
from __future__ import annotations

import time

from pipecat.frames.frames import (
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.processors.frame_processor import FrameDirection


class GravitreVoiceLatencyObserver(UserBotLatencyObserver):
    """UserBotLatencyObserver, made to actually fire on the live Flux path."""

    async def on_push_frame(self, data: FramePushed):
        if data.direction == FrameDirection.DOWNSTREAM:
            if isinstance(data.frame, ProposedUserStartedSpeakingFrame):
                # Mirror the stock class's VADUserStartedSpeakingFrame reset:
                # a fresh user turn is beginning, discard any stale timestamp
                # from a prior proposal that never resolved into a bot reply
                # (e.g. a suppressed backchannel — Phase 1).
                self._user_stopped_time = None
                self._user_turn_start_time = None
                self._user_turn = None
                self._reset_accumulators()
            elif (
                isinstance(data.frame, ProposedUserStoppedSpeakingFrame)
                and self._user_stopped_time is None
            ):
                # Earliest real "user's audio ended" signal on the Flux path.
                # VAD-based paths (if ever reintroduced) still set this more
                # precisely via VADUserStoppedSpeakingFrame in the stock
                # class, so this only fills the gap Flux otherwise leaves
                # empty (Flux has no VAD stacked — see pipeline.py).
                now = time.time()
                self._user_stopped_time = now
                self._user_turn_start_time = now

        await super().on_push_frame(data)
