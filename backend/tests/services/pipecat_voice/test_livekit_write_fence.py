"""RTC controls reach the canonical turn fence before a provider can start.

No connector is called. This exercises the real final write boundary and local
effect ledger; it is not live database audit or authorization certification.
"""
from types import SimpleNamespace
import json

import pytest

pytest.importorskip("livekit.rtc")

from app.services.pipecat_voice.livekit_candidate import LiveKitCandidateSocket
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
from app.services.voice_barge_in_write import begin_write_effect, write_effects_since
from app.services.tool_types import ToolValidationError


def packet(identity):
    return SimpleNamespace(participant=SimpleNamespace(identity=identity),
                           topic="gravitre-control", data=json.dumps({"type": "interrupt"}).encode())


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["interrupt", "disconnect"])
async def test_rtc_stop_refuses_actual_final_write_gate_and_records_block(event):
    socket = LiveKitCandidateSocket(SimpleNamespace(), participant_identity="authorized-peer")
    session = VoicePipelineSession()
    token = TurnCancellation()
    session.bind_turn_work(token)
    socket.voice_session = session
    ctx = SimpleNamespace(org_id="rtc-fence-" + event,
                          conversation_id="isolated-" + event, settings=SimpleNamespace())
    try:
        if event == "interrupt":
            socket._data_received(packet("authorized-peer"))
        else:
            socket._participant_disconnected(SimpleNamespace(identity="authorized-peer"))
        # The input queue has not been consumed, and no async pipeline task ran.
        assert token.cancelled
        with bound_turn_cancellation(token):
            with pytest.raises(ToolValidationError) as refused:
                begin_write_effect(ctx, "gmail.send")
        assert refused.value.code == "write_commit_interrupted"
        rows = write_effects_since(ctx.org_id, ctx.conversation_id, 0)
        assert rows and rows[-1]["status"] == "blocked"
        # A reconnect/new turn cannot reset the cancelled token.
        session.bind_turn_work(TurnCancellation())
        assert token.cancelled
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_foreign_rtc_stop_does_not_cancel_authorized_turn():
    socket = LiveKitCandidateSocket(SimpleNamespace(), participant_identity="authorized-peer")
    session = VoicePipelineSession()
    token = TurnCancellation()
    session.bind_turn_work(token)
    socket.voice_session = session
    try:
        socket._data_received(packet("foreign-peer"))
        socket._participant_disconnected(SimpleNamespace(identity="foreign-peer"))
        assert not token.cancelled
    finally:
        await socket.close()
