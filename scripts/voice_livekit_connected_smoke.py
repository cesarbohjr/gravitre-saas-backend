"""Connected RTC transport smoke; never certifies inference or voice quality.

Run on a host permitted to initialize LiveKit networking. The CI job starts a
loopback-only server and supplies public recorded speech. No production secrets.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import uuid
import wave

from livekit import api, rtc
import numpy as np


def load_socket():
    source = Path(__file__).resolve().parents[1] / "backend/app/services/pipecat_voice/livekit_candidate.py"
    spec = importlib.util.spec_from_file_location("candidate", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LiveKitCandidateSocket


def token(room: str, identity: str) -> str:
    # Public development credentials, valid only for this loopback CI server.
    return (api.AccessToken("devkey", "secret").with_identity(identity)
            .with_ttl(timedelta(minutes=5))
            .with_grants(api.VideoGrants(room_join=True, room=room)).to_jwt())


def read_pcm(path: Path, rate: int) -> bytes:
    with wave.open(str(path), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (rate, 1, 2):
            raise ValueError("expected mono PCM16 WAV at configured rate")
        return audio.readframes(audio.getnframes())


async def publish(source: rtc.AudioSource, pcm: bytes, rate: int) -> None:
    frame_bytes = rate // 50 * 2
    for pos in range(0, len(pcm), frame_bytes):
        chunk = pcm[pos:pos + frame_bytes]
        if chunk:
            await source.capture_frame(rtc.AudioFrame(chunk, rate, 1, len(chunk) // 2))
    await source.wait_for_playout()


async def connected_trial(url: str, input_pcm: bytes, output_pcm: bytes, out: Path) -> dict:
    room_name = "gravitre-isolated-" + uuid.uuid4().hex
    worker, peer, foreign = rtc.Room(), rtc.Room(), rtc.Room()
    rejoining = None
    socket = None
    source = None
    streams = []
    tasks = []
    received = bytearray()
    first_output = asyncio.Event()
    output_started_ns = None
    output_first_ns = None
    response_track_ready = asyncio.Event()

    async def capture(track):
        nonlocal output_first_ns
        stream = rtc.AudioStream(track, sample_rate=24000, num_channels=1)
        streams.append(stream)
        response_track_ready.set()
        async for event in stream:
            received.extend(bytes(event.frame.data))
            if output_first_ns is None and output_started_ns is not None:
                output_first_ns = time.monotonic_ns()
                first_output.set()

    def subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity == "candidate":
            tasks.append(asyncio.create_task(capture(track)))

    peer.on("track_subscribed", subscribed)
    started_ns = time.monotonic_ns()
    try:
        await worker.connect(url, token(room_name, "candidate"))
        socket = load_socket()(worker, participant_identity="recorded-peer")
        await socket.start()
        await peer.connect(url, token(room_name, "recorded-peer"))
        await asyncio.wait_for(response_track_ready.wait(), 15)
        print("RTC checkpoint: isolated participants connected", flush=True)
        joined_ms = (time.monotonic_ns() - started_ns) / 1e6

        # A genuinely connected third participant cannot inject tenant/action
        # identity or stop this participant's pipeline.
        await foreign.connect(url, token(room_name, "foreign-peer"))
        await foreign.local_participant.publish_data(
            b'{"type":"interrupt"}', reliable=True, topic="gravitre-control")
        await asyncio.sleep(0.2)
        if socket._pending_control is not None:
            raise AssertionError("foreign participant control accepted")

        source = rtc.AudioSource(16000, 1, queue_size_ms=100)
        track = rtc.LocalAudioTrack.create_audio_track("recorded-speech", source)
        await peer.local_participant.publish_track(
            track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
        deadline = asyncio.get_running_loop().time() + 15
        while socket._audio_task is None:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("candidate never subscribed to recorded peer")
            await asyncio.sleep(0.02)
        input_started_ns = time.monotonic_ns()
        sending = asyncio.create_task(publish(source, input_pcm, 16000))
        tasks.append(sending)
        first_input = json.loads((await asyncio.wait_for(socket.receive(), 15))["text"])
        if first_input.get("type") != "audio" or not base64.b64decode(first_input["pcm16_b64"]):
            raise AssertionError("recorded peer PCM never reached candidate")
        input_first_ms = (time.monotonic_ns() - input_started_ns) / 1e6
        # Drain inbound audio to avoid manufacturing a backpressure failure.
        async def drain():
            while True:
                await socket.receive()
        draining = asyncio.create_task(drain())
        tasks.append(draining)
        await sending
        print("RTC checkpoint: recorded speech ingress completed", flush=True)
        draining.cancel()
        await asyncio.gather(draining, return_exceptions=True)

        output_started_ns = time.monotonic_ns()
        frame_bytes = 24000 // 50 * 2
        for pos in range(0, len(output_pcm), frame_bytes):
            await socket.send_json({"type": "audio", "sample_rate": 24000,
                "num_channels": 1, "reply_id": 1,
                "pcm16_b64": base64.b64encode(output_pcm[pos:pos + frame_bytes]).decode()})
        await socket._source.wait_for_playout()
        await asyncio.wait_for(first_output.wait(), 15)
        await asyncio.sleep(0.3)
        if len(received) < 24000:
            raise AssertionError("less than half a second of output audio received")
        expected = np.frombuffer(output_pcm, dtype="<i2").astype(np.float64)
        actual = np.frombuffer(received, dtype="<i2").astype(np.float64)
        fft_size = 1 << (len(expected) + len(actual) - 1).bit_length()
        correlation = np.fft.irfft(np.fft.rfft(actual, fft_size) *
                                  np.conj(np.fft.rfft(expected, fft_size)), fft_size)
        energy = float(np.linalg.norm(expected) * np.linalg.norm(actual))
        normalized_correlation = float(np.max(correlation) / energy) if energy else 0.0
        # Signal identity/integrity, not conversational or perceptual quality.
        if normalized_correlation < 0.2:
            raise AssertionError("received audio does not correlate with recorded speech")
        print("RTC checkpoint: recorded speech egress and correlation passed", flush=True)
        with wave.open(str(out), "wb") as audio:
            audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            audio.writeframes(received)

        # Stop delivery measured at server adapter boundary, not acoustic cutoff
        # or cancellation of a production write; those remain separate gates.
        stop_started_ns = time.monotonic_ns()
        await peer.local_participant.publish_data(
            b'{"type":"interrupt"}', reliable=True, topic="gravitre-control")
        deadline = asyncio.get_running_loop().time() + 5
        while socket._pending_control is None:
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("interrupt did not reach candidate")
            await asyncio.sleep(0.005)
        stop_delivery_ms = (time.monotonic_ns() - stop_started_ns) / 1e6
        print("RTC checkpoint: pinned participant interrupt received", flush=True)
        await peer.disconnect()
        deadline = asyncio.get_running_loop().time() + 5
        while socket.client_state.name != "DISCONNECTED":
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("disconnect did not terminate candidate socket")
            await asyncio.sleep(0.01)
        if (await socket.receive())["type"] != "websocket.disconnect":
            raise AssertionError("disconnected session retained media authority")

        # Rejoin as a fresh peer; old socket must remain ended. This is RTC
        # rejoin latency only, not restored cognitive-session recovery.
        reconnect_started_ns = time.monotonic_ns()
        # A disconnected SDK Room owns disposed FFI resources. Use a fresh
        # instance instead of reconnecting that already-disposed object.
        rejoining = rtc.Room()
        await rejoining.connect(url, token(room_name, "recorded-peer"))
        rejoin_ms = (time.monotonic_ns() - reconnect_started_ns) / 1e6
        if socket.client_state.name != "DISCONNECTED":
            raise AssertionError("old session reactivated after peer rejoin")
        print("RTC checkpoint: fresh peer rejoined; old session remains closed", flush=True)
        return {"scope": "connected_livekit_rtc_transport_only",
            "join_ms": joined_ms, "input_first_frame_ms": input_first_ms,
            "output_first_frame_ms": (output_first_ns - output_started_ns) / 1e6,
            "interrupt_control_delivery_ms": stop_delivery_ms, "rtc_rejoin_ms": rejoin_ms,
            "foreign_control_rejected": True, "old_session_stays_closed": True,
            "output_duration_s": len(received) / 48000,
            "waveform_correlation": normalized_correlation,
            "output_rms_pcm16": float(np.sqrt(np.mean(actual * actual))),
            "output_clipped_fraction": float(np.mean(np.abs(actual) >= 32767)),
            "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "provider_inference": "NOT_RUN", "cancelled_write_audit": "NOT_RUN",
            "acoustic_interruption": "NOT_RUN", "conversational_audio_quality": "NOT_RUN",
            "certified": False}
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for stream in streams:
            await stream.aclose()
        if socket is not None:
            await socket.close()
        if source is not None:
            await source.aclose()
        await asyncio.gather(peer.disconnect(), foreign.disconnect(), worker.disconnect())
        if rejoining is not None:
            await rejoining.disconnect()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-wav", required=True, type=Path)
    parser.add_argument("--output-source-wav", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    manifest = {"certified": False, "status": "FAIL", "scope": "transport_only"}
    try:
        result = await asyncio.wait_for(connected_trial("ws://127.0.0.1:7880",
            read_pcm(args.input_wav, 16000), read_pcm(args.output_source_wav, 24000),
            args.artifacts / "livekit-received.wav"), timeout=90)
        manifest.update(status="PASS", result=result,
            input_sha256=hashlib.sha256(args.input_wav.read_bytes()).hexdigest())
    except Exception as exc:
        manifest["failure_category"] = type(exc).__name__
        import traceback
        manifest["failure_locations"] = [
            {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)
        ]
        raise
    finally:
        (args.artifacts / "transport-manifest.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps(manifest, sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
