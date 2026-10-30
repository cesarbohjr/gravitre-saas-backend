"""RTC SDK contract and safety tests. These do not certify live voice quality."""
import asyncio
import base64
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def load_candidate():
    path = Path(__file__).parents[2] / "app/services/pipecat_voice/livekit_candidate.py"
    spec = importlib.util.spec_from_file_location("livekit_candidate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packet(value, identity="replay-user", topic="gravitre-control"):
    return SimpleNamespace(participant=SimpleNamespace(identity=identity),
                           topic=topic, data=json.dumps(value).encode())


@pytest.fixture
def candidate_module():
    pytest.importorskip("livekit.rtc")
    return load_candidate()


@pytest.mark.asyncio
async def test_real_sdk_audio_source_accepts_pcm_and_closes(candidate_module):
    room = SimpleNamespace(local_participant=SimpleNamespace(publish_data=AsyncMock()))
    socket = candidate_module.LiveKitCandidateSocket(room, participant_identity="replay-user")
    try:
        await socket.send_json({"type": "audio", "sample_rate": 24000,
                                "num_channels": 1,
                                "pcm16_b64": base64.b64encode(bytes(960)).decode()})
        assert socket._source.sample_rate == 24000
        await socket.send_json({"type": "session.ready"})
        call = room.local_participant.publish_data.call_args
        assert call.kwargs["destination_identities"] == ["replay-user"]
    finally:
        await socket.close()
    assert (await socket.receive())["type"] == "websocket.disconnect"
    await socket.close()
    # Room disconnect callbacks may arrive after the source has been disposed.
    # An ended session must not send another FFI clear-buffer request.
    socket._source = SimpleNamespace(clear_queue=lambda: pytest.fail("disposed source accessed"))
    socket._disconnected()


@pytest.mark.asyncio
async def test_stop_preempts_full_audio_queue_and_ignores_foreign_controls(candidate_module):
    socket = candidate_module.LiveKitCandidateSocket(SimpleNamespace(), participant_identity="replay-user")
    try:
        for _ in range(100):
            socket._incoming.put_nowait({"type": "websocket.receive", "text": "audio"})
        for value, identity in [({"type": "interrupt"}, "other-tenant"),
                                 ({"type": "text", "text": "approve"}, "replay-user"),
                                 ({"type": "interrupt", "org_id": "other"}, "replay-user")]:
            socket._data_received(packet(value, identity))
        assert socket._pending_control is None
        socket._data_received(packet({"type": "interrupt"}))
        assert json.loads((await socket.receive())["text"]) == {"type": "interrupt"}
        assert socket._incoming.qsize() == 100
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_disconnect_wakes_blocked_receiver_and_discards_backlog(candidate_module):
    socket = candidate_module.LiveKitCandidateSocket(SimpleNamespace(), participant_identity="replay-user")
    try:
        waiting = asyncio.create_task(socket.receive())
        await asyncio.sleep(0)
        socket._participant_disconnected(SimpleNamespace(identity="foreign"))
        assert not waiting.done()
        socket._participant_disconnected(SimpleNamespace(identity="replay-user"))
        assert (await asyncio.wait_for(waiting, 1))["type"] == "websocket.disconnect"
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_invalid_pcm_is_rejected(candidate_module):
    socket = candidate_module.LiveKitCandidateSocket(SimpleNamespace(), participant_identity="replay-user")
    try:
        with pytest.raises(ValueError, match="PCM format"):
            await socket.send_json({"type": "audio", "sample_rate": 16000, "num_channels": 1})
        with pytest.raises(ValueError, match="PCM frame"):
            await socket.send_json({"type": "audio", "sample_rate": 24000, "num_channels": 1,
                                    "pcm16_b64": base64.b64encode(b"x").decode()})
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_candidate_requires_isolation_before_importing_runtime(candidate_module):
    with pytest.raises(ValueError, match="isolated mode"):
        await candidate_module.run_livekit_candidate(url="wss://unused", token="unused",
            participant_identity="replay-user", settings=None, org_id="test-org",
            user_id="test-user", conversation_id="test-conversation")


@pytest.mark.asyncio
async def test_reply_identity_and_valid_playback_reports_preserved(candidate_module):
    room = SimpleNamespace(local_participant=SimpleNamespace(publish_data=AsyncMock()))
    socket = candidate_module.LiveKitCandidateSocket(room, participant_identity="replay-user")
    try:
        await socket.send_json({"type": "audio", "sample_rate": 24000,
            "num_channels": 1, "reply_id": 7,
            "pcm16_b64": base64.b64encode(bytes(960)).decode()})
        assert json.loads(room.local_participant.publish_data.call_args.args[0]) == {
            "type": "audio.reply", "reply_id": 7}
        report = {"type": "playback.progress", "reply_id": 7,
                  "received_ms": 20, "played_ms": 10}
        socket._data_received(packet(report))
        assert json.loads((await socket.receive())["text"]) == report
        socket._data_received(packet({**report, "org_id": "foreign"}))
        socket._data_received(packet({**report, "played_ms": 30}))
        assert socket._incoming.empty()
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_native_audio_stream_encodes_real_pcm_without_altering_samples(candidate_module):
    socket = candidate_module.LiveKitCandidateSocket(SimpleNamespace(), participant_identity="replay-user")
    pcm = bytes(range(128)) * 5
    frame = candidate_module.rtc.AudioFrame(pcm, 16000, 1, len(pcm) // 2)
    async def stream():
        yield SimpleNamespace(frame=frame)
    socket._stream = stream()
    try:
        await socket._read_audio()
        value = json.loads(socket._incoming.get_nowait()["text"])
        assert value["sample_rate"] == 16000
        assert base64.b64decode(value["pcm16_b64"]) == pcm
        assert (await socket.receive())["type"] == "websocket.disconnect"
    finally:
        await socket.close()


@pytest.mark.asyncio
async def test_disconnect_cancels_pipeline_runner_instead_of_only_media(candidate_module):
    disconnected, stopped = asyncio.Event(), asyncio.Event()
    cancel = AsyncMock(side_effect=stopped.set)
    async def run():
        await stopped.wait()
    session = asyncio.create_task(candidate_module._run_until_disconnect(run(), disconnected, cancel))
    disconnected.set()
    await asyncio.wait_for(session, 1)
    cancel.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_failure_is_not_hidden_by_disconnect_monitor(candidate_module):
    async def run():
        raise RuntimeError("pipeline failed")
    cancel = AsyncMock()
    with pytest.raises(RuntimeError, match="pipeline failed"):
        await candidate_module._run_until_disconnect(run(), asyncio.Event(), cancel)
    cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_spoken_interruption_flushes_native_playout_before_event(candidate_module):
    order = []
    async def published(*args, **kwargs):
        order.append("published")
    room = SimpleNamespace(local_participant=SimpleNamespace(publish_data=published))
    socket = candidate_module.LiveKitCandidateSocket(room, participant_identity="replay-user")
    source = socket._source
    try:
        socket._source = SimpleNamespace(clear_queue=lambda: order.append("flushed"))
        await socket.send_json({"type": "event", "event": "speech.interrupted"})
        assert order == ["flushed", "published"]
    finally:
        socket._source = source
        await socket.close()

