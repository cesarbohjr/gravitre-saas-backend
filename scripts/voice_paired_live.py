"""Real WebSocket/RTC replay through the unchanged production cognitive pipeline.

Only the pinned acceptance database is allowed. Generated synthetic fixtures are
shared byte-for-byte. Reports distinguish observed audio from full certification.
"""
import asyncio
import base64
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

TARGET = "https://aadnwmjzrmbvadszroqt.supabase.co"
PROMPT = "Please explain why the sky is blue in two short sentences."


def guard(env):
    if env.get("GRAVITRE_VOICE_ISOLATED") != "1":
        raise ValueError("explicit isolated mode required")
    if any(env.get(k, "").rstrip("/") != TARGET for k in ("SUPABASE_URL", "E2E_SUPABASE_ALLOWED_URL")):
        raise ValueError("acceptance target mismatch")
    for name in ("ANTHROPIC_API_KEY", "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY",
                 "SUPABASE_SERVICE_ROLE_KEY", "PLATFORM_LIVE_BEARER_TOKEN",
                 "ISOLATED_CONVERSATION_TEST_ORG_ID", "ISOLATED_CONVERSATION_TEST_USER_ID"):
        if not env.get(name):
            raise ValueError("missing:" + name)


def wav(path, pcm, rate):
    with wave.open(str(path), "wb") as f:
        f.setparams((1, 2, rate, 0, "NONE", "PCM16"))
        f.writeframes(pcm)


class Capture:
    def __init__(self):
        self.pcm = bytearray()
        self.started = None
        self.first = None
        self.last = None
        self.events = {}

    def audio(self, pcm):
        import numpy as np
        self.pcm.extend(pcm)
        # RTC emits silence before synthesis. First packet is not first speech.
        if pcm and float(np.sqrt(np.mean(np.frombuffer(pcm, dtype="<i2").astype(float) ** 2))) > 100:
            now = time.monotonic()
            if self.started is not None and self.first is None:
                self.first = now
            self.last = now

    def event(self, message):
        kind = message.get("event") or message.get("type", "unknown")
        self.events[str(kind)] = self.events.get(str(kind), 0) + 1

    async def settle(self, running):
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            if running.done():
                await running
                raise RuntimeError("pipeline ended before completed reply")
            if self.first is not None and self.last and time.monotonic() - self.last > 4:
                return
            await asyncio.sleep(.1)
        raise TimeoutError("generated speech deadline")


async def stream_ws(ws, pcm):
    frame = 640
    start = time.monotonic()
    for offset in range(0, len(pcm), frame):
        await ws.send(json.dumps({"type": "audio", "sample_rate": 16000,
            "num_channels": 1, "pcm16_b64": base64.b64encode(pcm[offset:offset+frame]).decode()}))
        await asyncio.sleep(max(0, start + (offset + frame) / 32000 - time.monotonic()))


async def websocket_trial(settings, org, actor, cid, pcm, capture):
    from fastapi import FastAPI, WebSocket
    from pipecat.pipeline.runner import PipelineRunner
    from app.services.pipecat_voice.pipeline import build_pipecat_voice_task
    import uvicorn
    import websockets
    app = FastAPI()
    ready = asyncio.Event()
    tasks = []
    failure = []

    @app.websocket("/acceptance")
    async def endpoint(ws: WebSocket):
        # The controller's Auth API + membership preflight pins identity; the
        # loopback endpoint additionally requires the actual short-lived token.
        if ws.headers.get("authorization") != "Bearer " + os.environ["PLATFORM_LIVE_BEARER_TOKEN"]:
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            task, _ = build_pipecat_voice_task(websocket=ws, settings=settings,
                org_id=org, user_id=actor, conversation_id=cid)
            tasks.append(task)
            ready.set()
            await PipelineRunner(handle_sigint=False).run(task)
        except Exception as error:
            failure.append(type(error).__name__)
            ready.set()
            with contextlib.suppress(Exception):
                await ws.close(code=1011)

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8769, log_level="error"))
    serving = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            if serving.done():
                await serving
            await asyncio.sleep(.05)
        async with websockets.connect("ws://127.0.0.1:8769/acceptance?audio_origin=user_mic",
            additional_headers={"Authorization": "Bearer " + os.environ["PLATFORM_LIVE_BEARER_TOKEN"]}) as ws:
            await asyncio.wait_for(ready.wait(), 30)
            if failure:
                raise RuntimeError("pipeline_build:" + failure[0])
            async def receive():
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") == "audio":
                        capture.audio(base64.b64decode(message["pcm16_b64"]))
                    else:
                        capture.event(message)
            receiving = asyncio.create_task(receive())
            try:
                await asyncio.sleep(2)
                capture.started = time.monotonic()
                await stream_ws(ws, pcm + bytes(32000 * 2))
                await capture.settle(receiving)
            finally:
                receiving.cancel()
                await asyncio.gather(receiving, return_exceptions=True)
    finally:
        for task in tasks:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task.cancel(), 5)
        server.should_exit = True
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(serving, 10)


async def livekit_trial(settings, org, actor, cid, pcm, capture):
    from livekit import rtc
    from app.services.pipecat_voice.livekit_candidate import run_livekit_candidate
    from voice_livekit_connected_smoke import token, publish
    room_name = "paired-" + uuid.uuid4().hex
    peer = rtc.Room()
    streams, readers = [], []
    subscribed = asyncio.Event()
    async def read(track):
        stream = rtc.AudioStream(track, sample_rate=24000, num_channels=1)
        streams.append(stream)
        subscribed.set()
        async for event in stream:
            capture.audio(bytes(event.frame.data))
    def on_track(track, publication, participant):
        if participant.identity == "candidate" and track.kind == rtc.TrackKind.KIND_AUDIO:
            readers.append(asyncio.create_task(read(track)))
    peer.on("track_subscribed", on_track)
    peer.on("data_received", lambda packet: capture.event(json.loads(packet.data)) if packet.topic == "gravitre-events" else None)
    worker = asyncio.create_task(run_livekit_candidate(url="ws://127.0.0.1:7880",
        token=token(room_name, "candidate"), participant_identity="recorded-peer",
        settings=settings, org_id=org, user_id=actor, conversation_id=cid, isolated=True))
    source = None
    try:
        await peer.connect("ws://127.0.0.1:7880", token(room_name, "recorded-peer"))
        await asyncio.wait_for(subscribed.wait(), 30)
        source = rtc.AudioSource(16000, 1, queue_size_ms=100)
        track = rtc.LocalAudioTrack.create_audio_track("recorded-speech", source)
        await peer.local_participant.publish_track(track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
        await asyncio.sleep(2)
        capture.started = time.monotonic()
        await publish(source, pcm + bytes(32000 * 2), 16000)
        await capture.settle(worker)
    finally:
        await peer.disconnect()
        if source:
            await source.aclose()
        for stream in streams:
            await stream.aclose()
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        try:
            await asyncio.wait_for(worker, 10)
        except asyncio.TimeoutError:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


def independent_audit(client, org, cid, since):
    # Separate read-back, not the assistant's claim or an in-process ledger.
    rows = client.table("audit_events").select("id,action,resource_id").eq("org_id", org).gte("created_at", since).limit(1000).execute().data
    relevant = [r for r in rows if str(r.get("resource_id")) == cid]
    return {"scope": "durable audit_events for this conversation", "row_ids": [r["id"] for r in relevant],
            "actions": [r["action"] for r in relevant], "complete_window": len(rows) < 1000,
            "business_effect_sink_verified": False}


async def main():
    guard(os.environ)
    from supabase import create_client
    from app.config import get_settings
    import httpx
    import numpy as np
    output = Path("acceptance-results/paired-live")
    output.mkdir(parents=True, exist_ok=True)
    client = create_client(TARGET, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    actor = os.environ["ISOLATED_CONVERSATION_TEST_USER_ID"]
    org = os.environ["ISOLATED_CONVERSATION_TEST_ORG_ID"]
    if str(client.auth.get_user(os.environ["PLATFORM_LIVE_BEARER_TOKEN"]).user.id) != actor:
        raise ValueError("actor mismatch")
    membership = client.table("organization_members").select("user_id").eq("org_id", org).eq("user_id", actor).execute().data
    organization = client.table("organizations").select("settings").eq("id", org).single().execute().data
    if not membership or organization["settings"].get("never_customer_visible") is not True:
        raise ValueError("isolated membership missing")
    settings = get_settings()
    voice = os.environ.get("ELEVENLABS_VOICE_ID") or "EXAVITQu4vr4xnSDxMaL"
    with httpx.Client(timeout=45) as http:
        response = http.post("https://api.elevenlabs.io/v1/text-to-speech/" + voice,
            params={"output_format": "pcm_16000"}, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            json={"text": PROMPT, "model_id": "eleven_flash_v2_5"})
        if response.status_code != 200:
            raise RuntimeError("fixture_tts_http_" + str(response.status_code))
        pcm = response.content
    if not 3200 < len(pcm) < 1600000 or len(pcm) % 2:
        raise ValueError("fixture PCM bounds")
    wav(output / "input.wav", pcm, 16000)
    report = {"git_sha": os.environ.get("ACCEPTANCE_SOURCE_SHA"), "input_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "input_origin": "synthetic prerecorded speech, synthesized once for both transports", "trials": [],
        "certified": False, "human_quality_review": "NOT RUN", "write_governance_certification": "NOT RUN",
        "interruption": "NOT RUN", "reconnection": "NOT RUN"}
    for engine, trial in (("pipecat", websocket_trial), ("livekit", livekit_trial)):
        cid = str(uuid.uuid4())
        since = datetime.now(timezone.utc).isoformat()
        client.table("conversations").insert({"id": cid, "org_id": org, "user_id": actor, "title": "Internal acceptance " + engine}).execute()
        capture = Capture()
        row = {"engine": engine, "conversation_id": cid, "status": "FAIL"}
        try:
            await trial(settings, org, actor, cid, pcm, capture)
            samples = np.frombuffer(capture.pcm, dtype="<i2").astype(float)
            if capture.first is None or len(samples) < 2400:
                raise AssertionError("no generated speech")
            row.update(status="PASS", first_speech_from_input_start_ms=round((capture.first-capture.started)*1000, 2),
                first_speech_from_input_end_ms=round((capture.first-capture.started-len(pcm)/32000)*1000, 2),
                output_duration_s=len(samples)/24000, output_pcm_sha256=hashlib.sha256(capture.pcm).hexdigest(),
                rms=float(np.sqrt(np.mean(samples**2))), clipping_fraction=float(np.mean(abs(samples)>=32760)))
        except Exception as error:
            row.update(error_type=type(error).__name__)
            # Fixed stage diagnostics only; no provider bodies, transcripts or keys.
            print(engine + " failed: " + type(error).__name__, flush=True)
        finally:
            wav(output / (engine + ".wav"), capture.pcm, 24000)
            row["events"] = capture.events
            row["independent_audit"] = independent_audit(client, org, cid, since)
            report["trials"].append(row)
            (output / "manifest.json").write_text(json.dumps(report, indent=2))
    if not all(r["status"] == "PASS" for r in report["trials"]):
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
