"""Isolated LiveKit RTC transport for Gravitre's existing cognitive pipeline.

This is a transport comparison candidate, not an independent LiveKit Agents
orchestration engine. It deliberately reuses the production serializer and
pipeline, so room data cannot select a tenant or bypass execution authorization.
No production router imports this module. Install requirements-voice-comparison.txt.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from typing import Any

from livekit import rtc
from starlette.websockets import WebSocketState


class LiveKitCandidateSocket:
    """Adapt native RTC audio to the unchanged Pipecat WebSocket interface.

    The caller must mint room-scoped tokens for a dedicated isolated room and
    authenticate org/user before construction. Only one pinned participant may
    provide audio or control messages; server-origin and other participants are
    ignored. Disconnect ends the pipeline instead of retaining write authority.
    """

    def __init__(self, room: rtc.Room, *, participant_identity: str) -> None:
        if not participant_identity or not participant_identity.strip():
            raise ValueError("participant identity required")
        self.room = room
        self.participant_identity = participant_identity
        self.headers: dict[str, str] = {}
        # Replay exercises the real user-speech path; provenance is recorded by
        # the test controller, not an unsupported pipeline origin value.
        self.query_params = {"audio_origin": "user_mic"}
        self.client_state = WebSocketState.CONNECTED
        self.application_state = WebSocketState.CONNECTED
        self._incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._source = rtc.AudioSource(24000, 1, queue_size_ms=100)
        self._audio_task: asyncio.Task | None = None
        self._stream: rtc.AudioStream | None = None
        self._closed = False
        self.disconnected = asyncio.Event()
        self._audio_sid: str | None = None
        self._pending_control: dict[str, str] | None = None
        self._pending_audio: dict[str, Any] | None = None
        self._control_ready = asyncio.Event()
        self._output_reply_id: int | None = None

    async def start(self) -> None:
        self.room.on("track_subscribed", self._track_subscribed)
        self.room.on("data_received", self._data_received)
        self.room.on("participant_disconnected", self._participant_disconnected)
        self.room.on("disconnected", self._disconnected)
        track = rtc.LocalAudioTrack.create_audio_track("gravitre-response", self._source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await self.room.local_participant.publish_track(track, options)
        # Room.connect may subscribe before handlers are installed.
        for participant in self.room.remote_participants.values():
            for publication in participant.track_publications.values():
                if publication.track is not None:
                    self._track_subscribed(publication.track, publication, participant)

    def _track_subscribed(self, track, publication, participant) -> None:
        if self._closed or participant.identity != self.participant_identity:
            return
        if track.kind != rtc.TrackKind.KIND_AUDIO or self._audio_task is not None:
            return
        self._audio_sid = publication.sid
        self._stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1,
                                       capacity=100)
        self._audio_task = asyncio.create_task(self._read_audio())

    async def _read_audio(self) -> None:
        try:
            async for event in self._stream:
                frame = event.frame
                message = {"type": "audio", "sample_rate": frame.sample_rate,
                           "num_channels": frame.num_channels,
                           "pcm16_b64": base64.b64encode(bytes(frame.data)).decode("ascii")}
                # Backpressure bounds queued PCM and prevents silent frame loss.
                await self._incoming.put({"type": "websocket.receive",
                                          "text": json.dumps(message)})
        finally:
            self._end_session()

    def _data_received(self, packet) -> None:
        participant = packet.participant
        if self._closed or participant is None or participant.identity != self.participant_identity:
            return
        if packet.topic != "gravitre-control" or len(packet.data) > 4096:
            return
        try:
            value = json.loads(packet.data)
        except (ValueError, UnicodeError):
            return
        if not isinstance(value, dict):
            return
        if value.get("type") == "playback.progress":
            allowed = {"type", "reply_id", "received_ms", "played_ms", "interrupted", "final", "reason"}
            if set(value) - allowed:
                return
            if any(type(value.get(key)) is not int or value[key] < 0
                   for key in ("reply_id", "received_ms", "played_ms")):
                return
            if value["played_ms"] > value["received_ms"]:
                return
            # The canonical serializer validates/interprets the report. Reports
            # are telemetry only and never grant permission to execute tools.
            with contextlib.suppress(asyncio.QueueFull):
                self._incoming.put_nowait({"type": "websocket.receive", "text": json.dumps(value)})
            return
        # No text/tool/approval ingress. Recorded speech traverses STT and
        # the shared cognitive kernel. Never accept tenant identity in room data.
        if value != {"type": "interrupt"}:
            return
        self._source.clear_queue()
        # A reserved control slot prevents audio backpressure dropping a stop.
        self._pending_control = {"type": "websocket.receive", "text": json.dumps(value)}
        self._control_ready.set()

    def _participant_disconnected(self, participant) -> None:
        if participant.identity == self.participant_identity:
            self._end_session()

    def _disconnected(self, *_args) -> None:
        self._end_session()

    def _end_session(self) -> None:
        self.client_state = WebSocketState.DISCONNECTED
        self.application_state = WebSocketState.DISCONNECTED
        self._source.clear_queue()
        self._control_ready.set()
        self.disconnected.set()

    async def receive(self) -> dict[str, Any]:
        while self.client_state == WebSocketState.CONNECTED:
            if self._pending_control is not None:
                value, self._pending_control = self._pending_control, None
                self._control_ready.clear()
                return value
            if self._pending_audio is not None:
                value, self._pending_audio = self._pending_audio, None
                return value
            audio = asyncio.create_task(self._incoming.get())
            control = asyncio.create_task(self._control_ready.wait())
            try:
                done, _ = await asyncio.wait({audio, control}, return_when=asyncio.FIRST_COMPLETED)
                if self.client_state != WebSocketState.CONNECTED:
                    continue
                if control in done:
                    # If both completed, keep that audio behind the stop.
                    if audio in done and self.client_state == WebSocketState.CONNECTED:
                        self._pending_audio = audio.result()
                    continue
                return audio.result()
            finally:
                for pending in (audio, control):
                    if not pending.done():
                        pending.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await pending
        return {"type": "websocket.disconnect", "code": 1000}

    async def send_text(self, data: str) -> None:
        await self.send_json(json.loads(data))

    async def send_bytes(self, data: bytes) -> None:
        raise ValueError("candidate requires the existing JSON audio serializer")

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.client_state != WebSocketState.CONNECTED:
            return
        if message.get("type") == "audio":
            if message.get("sample_rate") != 24000 or message.get("num_channels") != 1:
                raise ValueError("unexpected output PCM format")
            if not isinstance(message.get("pcm16_b64"), str) or len(message["pcm16_b64"]) > 262144:
                raise ValueError("oversized or invalid PCM frame")
            pcm = base64.b64decode(message["pcm16_b64"], validate=True)
            if not pcm or len(pcm) % 2:
                raise ValueError("invalid PCM frame")
            reply_id = message.get("reply_id")
            if type(reply_id) is int and reply_id != self._output_reply_id:
                await self.room.local_participant.publish_data(
                    json.dumps({"type": "audio.reply", "reply_id": reply_id}).encode(),
                    reliable=True, topic="gravitre-events",
                    destination_identities=[self.participant_identity],
                )
                self._output_reply_id = reply_id
            await self._source.capture_frame(rtc.AudioFrame(pcm, 24000, 1, len(pcm) // 2))
        else:
            await self.room.local_participant.publish_data(
                json.dumps(message).encode(), reliable=True, topic="gravitre-events",
                destination_identities=[self.participant_identity],
            )

    async def close(self, code: int = 1000) -> None:
        if self._closed:
            return
        self._closed = True
        self._end_session()
        if self._audio_task is not None:
            self._audio_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._audio_task
        if self._stream is not None:
            await self._stream.aclose()
        await self._source.aclose()


async def run_livekit_candidate(*, url: str, token: str, participant_identity: str,
                                settings: Any, org_id: str, user_id: str,
                                conversation_id: str, isolated: bool = False) -> None:
    """Run one authenticated isolated session; never modifies runtime selection.

    Token and tenant arguments come from the trusted test controller, never
    participant metadata. A separate process/session is required after disconnect.
    """
    if isolated is not True:
        raise ValueError("LiveKit candidate requires explicit isolated mode")
    if not all(isinstance(v, str) and v.strip() for v in
               (url, token, participant_identity, org_id, user_id, conversation_id)):
        raise ValueError("authenticated isolated session configuration required")
    from pipecat.pipeline.runner import PipelineRunner
    from app.services.pipecat_voice.pipeline import build_pipecat_voice_task

    room = rtc.Room()
    socket = None
    task = None
    try:
        await room.connect(url, token)
        socket = LiveKitCandidateSocket(room, participant_identity=participant_identity)
        await socket.start()
        task, _meta = build_pipecat_voice_task(
            websocket=socket, settings=settings, org_id=org_id, user_id=user_id,
            conversation_id=conversation_id,
        )
        await _run_until_disconnect(PipelineRunner(handle_sigint=False).run(task),
                                    socket.disconnected, task.cancel)
    finally:
        if task is not None:
            await task.cancel()
        if socket is not None:
            await socket.close()
        await room.disconnect()


async def _run_until_disconnect(run, disconnected: asyncio.Event, cancel) -> None:
    """Transport disconnect alone doesn't stop PipelineRunner; cancel explicitly."""
    running = asyncio.create_task(run)
    lost = asyncio.create_task(disconnected.wait())
    try:
        done, _ = await asyncio.wait({running, lost}, return_when=asyncio.FIRST_COMPLETED)
        if lost in done and not running.done():
            await asyncio.wait_for(cancel(), timeout=5)
            try:
                await asyncio.wait_for(running, timeout=5)
            except asyncio.TimeoutError:
                pass
        else:
            await running
    finally:
        for pending in (running, lost):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(running, lost, return_exceptions=True)


def main() -> None:
    """Trusted-controller entry point; credentials stay in process environment."""
    import os
    if os.environ.get("GRAVITRE_VOICE_ISOLATED") != "1":
        raise SystemExit("GRAVITRE_VOICE_ISOLATED=1 is required")
    names = ("LIVEKIT_URL", "LIVEKIT_AGENT_TOKEN", "LIVEKIT_REPLAY_IDENTITY",
             "GRAVITRE_TEST_ORG_ID", "GRAVITRE_TEST_USER_ID", "GRAVITRE_TEST_CONVERSATION_ID")
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit("Missing isolated configuration: " + ", ".join(missing))
    from app.config import get_settings
    asyncio.run(run_livekit_candidate(
        url=os.environ["LIVEKIT_URL"], token=os.environ["LIVEKIT_AGENT_TOKEN"],
        participant_identity=os.environ["LIVEKIT_REPLAY_IDENTITY"],
        settings=get_settings(), org_id=os.environ["GRAVITRE_TEST_ORG_ID"],
        user_id=os.environ["GRAVITRE_TEST_USER_ID"],
        conversation_id=os.environ["GRAVITRE_TEST_CONVERSATION_ID"], isolated=True,
    ))


if __name__ == "__main__":
    main()
