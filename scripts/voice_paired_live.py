"""Real WebSocket/RTC replay through the unchanged production cognitive pipeline.

Only the pinned acceptance database is allowed. Generated synthetic fixtures are
shared byte-for-byte. Reports distinguish observed audio from full certification.
"""
import asyncio
import base64
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
import secrets
import subprocess
from pathlib import Path
import sys
import time
import traceback
import threading
from types import SimpleNamespace
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

TARGET = "https://aadnwmjzrmbvadszroqt.supabase.co"
CASE_ID = "provided_welcome_rewrite_v1"
PROMPT = ("Please rewrite this welcome note in a warmer tone, keeping the same meaning in two short sentences: "
          "Welcome to the team, Alex. We are happy you joined us.")


def interruption_cutoff_observations(capture, cancel_pcm=None):
    """Receiver PCM cutoff, strictly relative to interruption recording start."""
    last = capture.speech_by_reply.get(capture.interrupted_reply)
    cutoff = max(0, (last - capture.interrupt_at) * 1000) if last is not None else None
    result = dict(received_original_reply_cutoff_ms=cutoff, acoustic_physical_cutoff="NOT RUN",
        interruption_input_start_ms=round((capture.interrupt_at - capture.started) * 1000, 2),
        cutoff_limit_ms=500, cutoff_reference="interruption_input_start")
    if cancel_pcm is not None:
        # Keep the prior end-relative observation, but never extend the gate
        # by the phrase's duration or retroactively regrade earlier evidence.
        result["received_cutoff_from_cancel_input_end_ms"] = (
            cutoff - len(cancel_pcm) / 32 if cutoff is not None else None)
    if cutoff is None or cutoff > 500:
        result.update(status="FAIL", error_type="OriginalReplyCutoffExceeded")
    return result


class SanitizedDiagnostics(logging.Handler):
    def __init__(self, output):
        super().__init__(logging.ERROR)
        self.output = output
        self.rows = []
        # Pipecat uses Loguru; stdlib logging alone misses its error records.
        from loguru import logger
        self.loguru_sink = logger.add(self.emit_loguru, level='ERROR')

    def emit_loguru(self, message):
        record = message.record
        exception = record.get('exception')
        self.capture(record['message'], exception.type if exception else None,
                     exception.value if exception else None,
                     exception.traceback if exception else None)

    def emit(self, record):
        kind, error, tb = record.exc_info or (None, None, None)
        self.capture(record.getMessage(), kind, error, tb)

    def capture(self, text, kind, error, tb):
        if len(self.rows) >= 50:
            return
        message = (str(text) + ' ' + str(error or '')).lower()
        self.rows.append({"error_type": kind.__name__ if kind else None,
            'recognized_errors': [name for name in ('RuntimeError', 'TimeoutError', 'CancelledError',
                'APIConnectionError', 'ConnectError', 'ReadTimeout', 'APIStatusError', 'ValidationError',
                'AttributeError', 'TypeError', 'ValueError', 'AssertionError', 'ConnectionClosed')
                if name.lower() in message],
            "http_status": getattr(error, "status_code", None) if type(getattr(error, "status_code", None)) is int else None,
            "categories": [word for word in ("anthropic", "openai", "missing", "credit", "permission", "budget", "model", "column", "relation", "key", "settings", "illegal header", "bearer", "host header", "request line", "different loop", "event loop", "closed", "timeout", "deepgram", "elevenlabs") if word in message],
            "escaped_newline_in_diagnostic": '\\n' in message or '\\r' in message,
            "frames": [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                       for f in traceback.extract_tb(tb)[-40:]] if tb else []})
        self.output.write_text(json.dumps(self.rows, indent=2))


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


def verified_fixture(path, expected_hash):
    with wave.open(str(path), 'rb') as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError('recorded fixture format mismatch')
        pcm = source.readframes(source.getnframes())
    if hashlib.sha256(pcm).hexdigest() != expected_hash:
        raise ValueError('recorded fixture digest mismatch')
    return pcm


class FinalFenceProbe:
    """A real worker waits across cancellation before the canonical final gate.

    This exercises the final fence only, not approval issuance or the full tool
    invoker. The provider is an independent loopback fixture, never Gmail.
    """
    def __init__(self, *, settings, org, actor, cid, sink_token, logical_id):
        self.ctx = SimpleNamespace(settings=settings, org_id=org, actor_id=actor, conversation_id=cid)
        self.sink_token = sink_token
        self.logical_id = logical_id
        self.release = threading.Event()
        self.started = threading.Event()

    def run(self, token):
        import http.client
        from app.services.turn_cancellation import bound_turn_cancellation
        from app.services.voice_barge_in_write import begin_write_effect, finish_write_effect
        from app.services.tool_types import ToolValidationError
        with bound_turn_cancellation(token):
            self.started.set()
            if not self.release.wait(15):
                raise TimeoutError('fixture worker release deadline')
            # Exercise the native repository independently of the connector
            # final fence. A cancelled audio turn must stop both boundaries.
            from app.core.db import get_supabase_client
            from app.operators.agent_jobs import create_job
            native_client = get_supabase_client(self.ctx.settings)
            native = {'native_insert_blocked': False}
            try:
                job = create_job(native_client, self.ctx.org_id,
                    environment='acceptance', max_attempts=1,
                    payload={'acceptance_trace': self.ctx.conversation_id,
                        'case': self.logical_id, 'task': 'Synthetic audio cancellation sentinel. Do not execute.'})
                native['native_job_id'] = str(job['id'])
                # No worker or notification fanout: this row is only an insert
                # witness and must never remain queued for later execution.
                native_client.table('agent_jobs').update({'status': 'cancelled'}).eq('org_id', self.ctx.org_id).eq('id', job['id']).execute()
            except ToolValidationError as error:
                native.update(native_insert_blocked=True, native_error_code=error.code)
            try:
                handle = begin_write_effect(self.ctx, 'gmail.send')
            except ToolValidationError as error:
                return {'gate_blocked': True, 'gate_error_code': error.code,
                        'scope': 'canonical final write fence with fixture provider', **native}
            if handle is None:
                raise AssertionError('write gate did not recognize mutating catalog action')
            body = dict(org_id=self.ctx.org_id, actor_id=self.ctx.actor_id,
                        logical_id=self.logical_id, action='acceptance.note.create',
                        payload={'note': 'fixed synthetic acceptance effect'})
            connection = http.client.HTTPConnection('127.0.0.1', 8771, timeout=5)
            try:
                connection.request('POST', '/effects', json.dumps(body),
                    {'Authorization': 'Bearer ' + self.sink_token, 'Content-Type': 'application/json'})
                response = connection.getresponse()
                response.read()
                if response.status != 200:
                    raise AssertionError('fixture provider refused positive scope')
            finally:
                connection.close()
            finish_write_effect(handle, 'completed')
            return {'gate_blocked': False, 'scope': 'canonical final write fence with fixture provider', **native}


class Capture:
    def __init__(self):
        self.pcm = bytearray()
        self.started = None
        self.first = None
        self.last = None
        self.events = {}
        self.event_timeline = []
        self.interruption_timeline = []
        self.turn_complete_at = None
        self.last_bot_stop_at = None
        self.authorization = {}
        self.scenario = "baseline"
        self.reply_id = None
        self.speech_by_reply = {}
        self.interrupt_at = None
        self.interrupted_reply = None
        self.errors = []
        self.timeout_tasks = []
        self.cancel_recognized = False
        self.backchannel_recognized = False
        self.backchannel_original_token = None
        self.backchannel_cancelled_at_completion = None
        self.voice_session = None
        self.probe = None
        self.probe_result = None

    def bind_voice_session(self, session):
        self.voice_session = session
        session.interruption_timing_sink = self.note_interruption_stage

    def note_interruption_stage(self, stage, details):
        if self.started is not None and len(self.interruption_timeline) < 240:
            self.interruption_timeline.append({'stage': stage,
                'from_input_start_ms': round((time.monotonic() - self.started) * 1000, 2),
                **details})

    def audio(self, pcm, reply_id=None):
        import numpy as np
        if reply_id is not None:
            self.reply_id = reply_id
        self.pcm.extend(pcm)
        # RTC emits silence before synthesis. First packet is not first speech.
        if pcm and float(np.sqrt(np.mean(np.frombuffer(pcm, dtype="<i2").astype(float) ** 2))) > 100:
            now = time.monotonic()
            if self.started is not None and self.first is None:
                self.first = now
            self.last = now
            self.speech_by_reply[self.reply_id] = now

    def event(self, message):
        if message.get("type") == "transcript" and message.get("final") is True:
            from app.services.spoken_write_approval import classify_spoken_write_approval
            decision = classify_spoken_write_approval(str(message.get("text") or ""))
            if decision.decision == "reject" and decision.invoke_allowed is False:
                self.cancel_recognized = True
            if self.scenario == 'backchannel':
                from app.services.pipecat_voice.backchannel_classifier import classify_user_utterance, is_backchannel
                if is_backchannel(classify_user_utterance(str(message.get('text') or ''))):
                    self.backchannel_recognized = True
        if message.get("type") == "audio.reply":
            self.reply_id = message.get("reply_id")
        kind = message.get("event") or message.get("type", "unknown")
        if kind == 'assistant_turn.complete':
            self.turn_complete_at = time.monotonic()
        elif kind == 'bot-stopped-speaking':
            self.last_bot_stop_at = time.monotonic()
        if self.started is not None and kind in {
            'user-started-speaking', 'user-stopped-speaking', 'transcript',
            'speech.duck', 'speech.unduck', 'speech.interrupted', 'audio.reply',
            'assistant_turn.complete', 'bot-started-speaking', 'bot-stopped-speaking',
        } and len(self.event_timeline) < 200:
            # Timing only: transcript text and provider/credential bodies are
            # deliberately excluded from portable diagnostic artifacts.
            self.event_timeline.append({'event': kind,
                'from_input_start_ms': round((time.monotonic() - self.started) * 1000, 2),
                'reply_id': message.get('reply_id') if type(message.get('reply_id')) is int else None,
                'final': message.get('final') if type(message.get('final')) is bool else None})
        self.events[str(kind)] = self.events.get(str(kind), 0) + 1
        if kind == "error":
            text = json.dumps(message).lower()
            self.errors.append({"fields": sorted(message), "categories": [word for word in
                ("anthropic", "openai", "deepgram", "elevenlabs", "401", "403", "429", "credit",
                 "missing", "model", "permission", "budget", "settings", "validation", "database", "timeout")
                if word in text]})

    async def interrupt(self, send, running):
        deadline = time.monotonic() + 75
        while self.first is None:
            if running.done():
                await running
                raise RuntimeError("session ended before interruption trial")
            if time.monotonic() > deadline:
                raise TimeoutError("no generated speech to interrupt")
            await asyncio.sleep(.01)
        await asyncio.sleep(.25)
        probe_task = None
        token = None
        if self.probe is not None:
            token = getattr(self.voice_session, 'turn_cancellation', None)
            if token is None or token.cancelled:
                raise AssertionError('no uncancelled original turn token to fence')
            probe_task = asyncio.create_task(asyncio.to_thread(self.probe.run, token))
            deadline = time.monotonic() + 5
            while not self.probe.started.is_set():
                if probe_task.done():
                    await probe_task
                if time.monotonic() > deadline:
                    self.probe.release.set()
                    raise TimeoutError('fixture worker startup')
                await asyncio.sleep(.005)
        self.interrupted_reply = self.reply_id
        self.interrupt_at = time.monotonic()
        try:
            await send()
            if token is not None:
                deadline = time.monotonic() + 5
                while not token.cancelled and time.monotonic() < deadline:
                    await asyncio.sleep(.01)
        finally:
            if self.probe is not None:
                self.probe.release.set()
            if probe_task is not None:
                self.probe_result = await asyncio.wait_for(probe_task, 10)
                self.probe_result['original_token_cancelled'] = bool(token.cancelled)

    async def backchannel(self, send, running):
        deadline = time.monotonic() + 75
        while self.first is None:
            if running.done():
                await running
                raise RuntimeError('session ended before backchannel trial')
            if time.monotonic() > deadline:
                raise TimeoutError('no speech for backchannel trial')
            await asyncio.sleep(.01)
        await asyncio.sleep(.25)
        self.backchannel_original_token = getattr(self.voice_session, 'turn_cancellation', None)
        if self.backchannel_original_token is None or self.backchannel_original_token.cancelled:
            raise AssertionError('no active original turn for backchannel')
        await send()

    async def settle(self, running):
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            if running.done():
                await running
                raise RuntimeError("pipeline ended before completed reply")
            completed = self.events.get("bot-llm-stopped", 0) and self.events.get("bot-stopped-speaking", 0)
            if self.scenario in {"baseline", "reconnect", "backchannel"}:
                completed = (completed and self.turn_complete_at is not None
                    and self.last_bot_stop_at is not None
                    and self.last_bot_stop_at >= self.turn_complete_at)
            if self.scenario == "spoken_cancel":
                completed = completed and self.cancel_recognized
            if completed and self.first is not None and self.last and time.monotonic() - self.last > 4:
                if self.scenario == 'backchannel':
                    # Snapshot while the session is still connected. RTC
                    # teardown correctly cancels its token afterward, which
                    # must not rewrite the completed backchannel observation.
                    self.backchannel_cancelled_at_completion = (
                        self.backchannel_original_token is None
                        or self.backchannel_original_token.cancelled)
                return
            await asyncio.sleep(.1)
        # Capture code locations only, never task reprs, locals or arguments.
        for task in list(asyncio.all_tasks())[:200]:
            frames = []
            coroutine = task.get_coro()
            for _ in range(40):
                frame = getattr(coroutine, 'cr_frame', None) or getattr(coroutine, 'gi_frame', None)
                if frame is not None:
                    frames.append({'file': Path(frame.f_code.co_filename).name,
                        'function': frame.f_code.co_name, 'line': frame.f_lineno})
                coroutine = getattr(coroutine, 'cr_await', None) or getattr(coroutine, 'gi_yieldfrom', None)
                if coroutine is None:
                    break
            self.timeout_tasks.append({'frames': frames})
        raise TimeoutError("generated speech deadline")


async def stream_ws(ws, pcm):
    frame = 640
    start = time.monotonic()
    for offset in range(0, len(pcm), frame):
        await ws.send(json.dumps({"type": "audio", "sample_rate": 16000,
            "num_channels": 1, "pcm16_b64": base64.b64encode(pcm[offset:offset+frame]).decode()}))
        await asyncio.sleep(max(0, start + (offset + frame) / 32000 - time.monotonic()))


async def websocket_trial(settings, org, actor, cid, pcm, capture, cancel_pcm=None, backchannel_pcm=None):
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
            capture.bind_voice_session(task.gravitre_voice_session)
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
        try:
            async with websockets.connect("ws://127.0.0.1:8769/acceptance",
                additional_headers={"Authorization": "Bearer invalid-acceptance-token"}):
                raise AssertionError("unauthenticated controller WebSocket accepted")
        except websockets.exceptions.InvalidStatus as error:
            if error.response.status_code != 403:
                raise
            capture.authorization["invalid_websocket_token_denied"] = True
        async with websockets.connect("ws://127.0.0.1:8769/acceptance?audio_origin=user_mic",
            additional_headers={"Authorization": "Bearer " + os.environ["PLATFORM_LIVE_BEARER_TOKEN"]}) as ws:
            await asyncio.wait_for(ready.wait(), 30)
            if failure:
                raise RuntimeError("pipeline_build:" + failure[0])
            async def receive():
                async for raw in ws:
                    message = json.loads(raw)
                    if message.get("type") == "audio":
                        capture.audio(base64.b64decode(message["pcm16_b64"]), message.get("reply_id"))
                    else:
                        capture.event(message)
            receiving = asyncio.create_task(receive())
            try:
                await asyncio.sleep(2)
                capture.started = time.monotonic()
                await stream_ws(ws, pcm + bytes(32000 * 2))
                if capture.scenario == "interrupt":
                    await capture.interrupt(lambda: ws.send(json.dumps({"type": "interrupt"})), receiving)
                elif capture.scenario == "spoken_cancel":
                    await capture.interrupt(lambda: stream_ws(ws, cancel_pcm + bytes(32000 * 2)), receiving)
                elif capture.scenario == 'backchannel':
                    await capture.backchannel(lambda: stream_ws(ws, backchannel_pcm + bytes(32000 * 2)), receiving)
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


async def livekit_trial(settings, org, actor, cid, pcm, capture, cancel_pcm=None, backchannel_pcm=None):
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
        settings=settings, org_id=org, user_id=actor, conversation_id=cid, isolated=True,
        session_observer=capture.bind_voice_session))
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
        if capture.scenario == "interrupt":
            await capture.interrupt(lambda: peer.local_participant.publish_data(
                b'{"type":"interrupt"}', reliable=True, topic="gravitre-control"), worker)
        elif capture.scenario == "spoken_cancel":
            await capture.interrupt(lambda: publish(source, cancel_pcm + bytes(32000 * 2), 16000), worker)
        elif capture.scenario == 'backchannel':
            await capture.backchannel(lambda: publish(source, backchannel_pcm + bytes(32000 * 2), 16000), worker)
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
    output = Path(os.environ.get('ACCEPTANCE_ARTIFACT_DIR', 'acceptance-results/paired-live'))
    output.mkdir(parents=True, exist_ok=True)
    logging.getLogger().addHandler(SanitizedDiagnostics(output / "pipeline-failures.json"))
    client = create_client(TARGET, os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    actor = os.environ["ISOLATED_CONVERSATION_TEST_USER_ID"]
    org = os.environ["ISOLATED_CONVERSATION_TEST_ORG_ID"]
    if str(client.auth.get_user(os.environ["PLATFORM_LIVE_BEARER_TOKEN"]).user.id) != actor:
        raise ValueError("actor mismatch")
    membership = client.table("organization_members").select("user_id").eq("org_id", org).eq("user_id", actor).execute().data
    organization = client.table("organizations").select("settings").eq("id", org).single().execute().data
    if (not membership or organization["settings"].get("never_customer_visible") is not True
            or organization["settings"].get("isolated_conversation_test_org") is not True):
        raise ValueError("isolated membership missing")
    settings = get_settings()
    if settings.supabase_url.rstrip('/') != TARGET or settings.supabase_service_role_key != os.environ['SUPABASE_SERVICE_ROLE_KEY'].strip():
        raise ValueError('canonical database settings differ from controller')
    from app.core.db import get_supabase_client
    canonical = get_supabase_client(settings)
    header_checks = []
    def inspect_headers(request):
        headers = request.headers
        header_checks.append({
            'target_is_acceptance': request.url.host == 'aadnwmjzrmbvadszroqt.supabase.co',
            'apikey_matches_configured_service_key': headers.get('apikey') == settings.supabase_service_role_key,
            'authorization_matches_configured_service_key': headers.get('authorization') == 'Bearer ' + settings.supabase_service_role_key,
            'authorization_is_empty_bearer': headers.get('authorization', '').strip().lower() == 'bearer',
            'header_has_control_character': any(any(ord(c) < 32 or ord(c) == 127 for c in value) for value in headers.values()),
            'header_has_trailing_whitespace': any(value != value.rstrip() for value in headers.values()),
        })
        (output / 'canonical-db-header-checks.json').write_text(json.dumps(header_checks[-30:], indent=2))
    canonical.postgrest.session.event_hooks.setdefault('request', []).append(inspect_headers)
    canonical.table('organizations').select('id').eq('id', org).limit(1).execute()
    import atexit
    import http.client
    sink_path = output / 'write-sink.sqlite'
    sink_token = secrets.token_urlsafe(32)
    sink_script = Path(__file__).with_name('voice_acceptance_sink.py')
    sink_process = subprocess.Popen([sys.executable, str(sink_script), '--db', str(sink_path),
        '--org', org, '--actor', actor, '--port', '8771'],
        env={'GRAVITRE_VOICE_ISOLATED': '1', 'ACCEPTANCE_SINK_TOKEN': sink_token},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def stop_sink():
        if sink_process.poll() is None:
            sink_process.terminate()
            try:
                sink_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                sink_process.kill()
                sink_process.wait(timeout=3)
    atexit.register(stop_sink)
    for _ in range(100):
        if sink_process.poll() is not None:
            raise RuntimeError('fixture sink exited')
        connection = http.client.HTTPConnection('127.0.0.1', 8771, timeout=.2)
        try:
            connection.request('GET', '/')
            connection.getresponse().read()
            break
        except OSError:
            await asyncio.sleep(.05)
        finally:
            connection.close()
    else:
        raise TimeoutError('fixture sink startup')
    from app.services.turn_cancellation import TurnCancellation
    positive = FinalFenceProbe(settings=settings, org=org, actor=actor,
        cid=str(uuid.uuid4()), sink_token=sink_token, logical_id='positive-control')
    positive.release.set()
    positive_result = await asyncio.to_thread(positive.run, TurnCancellation())
    if positive_result['gate_blocked']:
        raise AssertionError('fixture positive control blocked')
    pcm = verified_fixture(os.environ['ACCEPTANCE_INPUT_WAV'],
        'bd1062d37671b640cf0be2ae4397d3c133bd23131ac2d6f568c1ec1c076e3731')
    cancel_pcm = verified_fixture(os.environ['ACCEPTANCE_CANCEL_WAV'],
        'cb59c58a686767cc7fc882ac6773dbd09beed5c22d420a229524f8a55a2c4936')
    backchannel_pcm = verified_fixture(Path(os.environ['ACCEPTANCE_NATIVE_RECORDINGS_DIR']) / 'approve.wav',
        '91e37080c6122a0e5df30858e72bffcbeb34e4a4415597771f7fa78382bb2133')
    if not 3200 < len(pcm) < 1600000 or len(pcm) % 2:
        raise ValueError("fixture PCM bounds")
    wav(output / "input.wav", pcm, 16000)
    if not 3200 < len(cancel_pcm) < 320000 or len(cancel_pcm) % 2:
        raise ValueError("cancel fixture PCM bounds")
    wav(output / "cancel-input.wav", cancel_pcm, 16000)
    wav(output / 'backchannel-input.wav', backchannel_pcm, 16000)
    report = {"git_sha": os.environ.get("ACCEPTANCE_SOURCE_SHA"), "input_pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "case_id": CASE_ID,
        "cancel_input_pcm_sha256": hashlib.sha256(cancel_pcm).hexdigest(),
        'backchannel_input_pcm_sha256': hashlib.sha256(backchannel_pcm).hexdigest(),
        "fixture_positive_control": positive_result,
        "runtime_versions": {name: importlib.metadata.version(name) for name in ('pipecat-ai', 'livekit', 'supabase', 'httpx', 'anthropic')},
        "configured_providers": {'inference': settings.preferred_ai_provider,
            'stt': settings.voice_pipecat_stt, 'tts_model': settings.elevenlabs_tts_model},
        "livekit_server": '1.13.11 loopback only',
        "input_origin": "pinned synthetic recordings from run 41134456513 artifact 13017080382", "trials": [],
        "certified": False, "human_quality_review": "NOT RUN", "write_governance_certification": "NOT RUN",
        "interruption": "NOT RUN", "reconnection": "NOT RUN"}
    conversations = {}
    baselines = {}
    for scenario, engine, trial in ((scenario, engine, trial) for scenario in ("baseline", "backchannel", "interrupt", "spoken_cancel", "reconnect")
            for engine, trial in (("pipecat", websocket_trial), ("livekit", livekit_trial))):
        if scenario != "baseline" and not baselines.get(engine):
            report["trials"].append({"engine": engine, "scenario": scenario, "status": "NOT RUN",
                "blocker": "baseline_generated_answer_failed"})
            (output / "manifest.json").write_text(json.dumps(report, indent=2))
            continue
        cid = conversations.get(engine) if scenario == "reconnect" else str(uuid.uuid4())
        if not cid:
            raise RuntimeError("missing initial conversation for reconnect")
        since = datetime.now(timezone.utc).isoformat()
        if scenario != "reconnect":
            client.table("conversations").insert({"id": cid, "org_id": org, "user_id": actor, "title": "Internal acceptance " + engine}).execute()
        if scenario == "baseline":
            conversations[engine] = cid
        capture = Capture()
        capture.scenario = scenario
        if scenario in {'interrupt', 'spoken_cancel'}:
            capture.probe = FinalFenceProbe(settings=settings, org=org, actor=actor,
                cid=cid, sink_token=sink_token, logical_id='late-write-' + cid)
        row = {"engine": engine, "scenario": scenario, "conversation_id": cid, "status": "FAIL"}
        before_roles = [r["role"] for r in client.table("conversation_messages").select("role").eq("conversation_id", cid).execute().data]
        row["durable_messages_before"] = len(before_roles)
        trial_started = time.monotonic()
        try:
            await trial(settings, org, actor, cid, pcm, capture, cancel_pcm, backchannel_pcm)
            samples = np.frombuffer(capture.pcm, dtype="<i2").astype(float)
            if capture.first is None or len(samples) < 2400:
                raise AssertionError("no generated speech")
            row.update(status="PASS", first_speech_from_input_start_ms=round((capture.first-capture.started)*1000, 2),
                session_start_to_first_speech_ms=round((capture.first-trial_started)*1000, 2),
                first_speech_from_input_end_ms=round((capture.first-capture.started-len(pcm)/32000)*1000, 2),
                output_duration_s=len(samples)/24000, output_pcm_sha256=hashlib.sha256(capture.pcm).hexdigest(),
                rms=float(np.sqrt(np.mean(samples**2))), clipping_fraction=float(np.mean(abs(samples)>=32760)))
            if capture.interrupt_at is not None:
                row.update(interruption_cutoff_observations(
                    capture, cancel_pcm if scenario == 'spoken_cancel' else None))
        except Exception as error:
            row.update(error_type=type(error).__name__,
                error_frames=[{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                              for f in traceback.extract_tb(error.__traceback__)[-8:]])
            # Fixed stage diagnostics only; no provider bodies, transcripts or keys.
            print(engine + " failed: " + type(error).__name__, flush=True)
        finally:
            audio_path = output / (engine + "-" + scenario + ".wav")
            wav(audio_path, capture.pcm, 24000)
            if row["status"] == "PASS" and scenario not in {"interrupt", "spoken_cancel"}:
                with httpx.Client(timeout=45) as http:
                    speech = http.post("https://api.deepgram.com/v1/listen", params={"model": "nova-3"},
                        headers={"Authorization": "Token " + os.environ["DEEPGRAM_API_KEY"], "Content-Type": "audio/wav"},
                        content=audio_path.read_bytes())
                    if speech.status_code != 200:
                        row.update(status="FAIL", output_stt_http_status=speech.status_code)
                    else:
                        row['output_transcription_request_id'] = speech.json().get('metadata', {}).get('request_id')
                        transcript = speech.json()["results"]["channels"][0]["alternatives"][0]["transcript"].lower()
                        # This case contains fixed synthetic welcome text only;
                        # retain its generated transcript for content/quality QA.
                        row['synthetic_output_transcript'] = transcript[:3000]
                        valid = ("alex" in transcript and "team" in transcript and
                            any(word in transcript for word in ("welcome", "happy", "glad", "excited", "thrilled")) and
                            not any(phrase in transcript for phrase in ("can't answer", "cannot answer", "not configured", "knowledge base")))
                        row["answer_content_valid"] = valid
                        if not valid:
                            row.update(status="FAIL", error_type="GeneratedAnswerContentMismatch")
            row["events"] = capture.events
            row["event_timeline"] = capture.event_timeline
            row['interruption_timeline'] = capture.interruption_timeline
            row["pipeline_errors"] = capture.errors
            row['timeout_tasks'] = capture.timeout_tasks
            if capture.errors:
                row.update(status="FAIL", error_type="PipelineErrorEvent")
            row["authorization"] = capture.authorization
            if capture.probe is not None:
                row['final_write_fence_probe'] = capture.probe_result
                evidence = json.loads(subprocess.run([sys.executable, str(sink_script), '--db', str(sink_path), '--audit'],
                    check=True, capture_output=True, text=True).stdout)
                attempts = [r for r in evidence['attempts'] if r['logical_id'] == capture.probe.logical_id]
                effects = [r for r in evidence['effects'] if r['logical_id'] == capture.probe.logical_id]
                row['independent_fixture_attempts'] = len(attempts)
                row['independent_fixture_effects'] = len(effects)
                native_rows = client.table('agent_jobs').select('id,status').eq('org_id', org).contains('payload', {'acceptance_trace': cid}).execute().data
                row['independent_native_job_ids'] = [r['id'] for r in native_rows]
                row['independent_native_effects'] = len(native_rows)
                valid_fence = (capture.probe_result and capture.probe_result.get('gate_blocked') is True
                    and capture.probe_result.get('original_token_cancelled') is True
                    and capture.probe_result.get('native_insert_blocked') is True
                    and capture.probe_result.get('native_error_code') == 'write_commit_interrupted'
                    and not native_rows and not attempts and not effects)
                if not valid_fence:
                    row.update(status='FAIL', error_type='FinalWriteFenceNotIndependentlyVerified')
                (output / 'write-sink-audit.json').write_text(json.dumps(evidence, indent=2))
            if scenario == "spoken_cancel":
                row["cancel_stt_classified_as_reject"] = capture.cancel_recognized
                if not capture.cancel_recognized:
                    row.update(status="FAIL", error_type="CancelSpeechNotRecognized")
            after_roles = [r["role"] for r in client.table("conversation_messages").select("role").eq("conversation_id", cid).execute().data]
            row["durable_messages_after"] = len(after_roles)
            if scenario == 'backchannel':
                row['backchannel_recognized'] = capture.backchannel_recognized
                row['backchannel_verdict_phase'] = 'completed_reply_before_transport_teardown'
                row['original_work_cancelled'] = capture.backchannel_cancelled_at_completion
                row['original_work_cancelled_after_teardown'] = (
                    capture.backchannel_original_token is None
                    or capture.backchannel_original_token.cancelled)
                if (not capture.backchannel_recognized or row['original_work_cancelled'] is not False
                        or len(after_roles) != 2 or capture.events.get('assistant_turn.complete') != 1):
                    row.update(status='FAIL', error_type='BackchannelInterruptedOrBecameANewTurn')
            if scenario == "reconnect":
                row["durable_prior_user_and_assistant_present"] = all(role in before_roles for role in ("user", "assistant"))
                if not row["durable_prior_user_and_assistant_present"]:
                    row.update(status="FAIL", error_type="MissingDurablePriorConversation")
            row["independent_audit"] = independent_audit(client, org, cid, since)
            if scenario == "baseline":
                baselines[engine] = row["status"] == "PASS"
            report["trials"].append(row)
            report["interruption"] = "MEASURED_RECEIVER_PCM_ONLY" if any(r.get("received_original_reply_cutoff_ms") is not None for r in report["trials"]) else "NOT RUN"
            report["reconnection"] = "FRESH_SESSION_SAME_CONVERSATION" if any(r["scenario"] == "reconnect" for r in report["trials"]) else "NOT RUN"
            (output / "manifest.json").write_text(json.dumps(report, indent=2))
    evidence = json.loads(subprocess.run([sys.executable, str(sink_script), '--db', str(sink_path), '--audit'],
        check=True, capture_output=True, text=True).stdout)
    (output / 'write-sink-audit.json').write_text(json.dumps(evidence, indent=2))
    positive_attempts = [r for r in evidence['attempts'] if r['logical_id'] == 'positive-control']
    positive_effects = [r for r in evidence['effects'] if r['logical_id'] == 'positive-control']
    report['fixture_positive_control']['independent_attempts'] = len(positive_attempts)
    report['fixture_positive_control']['independent_effects'] = len(positive_effects)
    native_positive = client.table('agent_jobs').select('id,status').eq('org_id', org).contains('payload', {'acceptance_trace': positive.ctx.conversation_id}).execute().data
    report['fixture_positive_control']['independent_native_rows'] = native_positive
    (output / 'manifest.json').write_text(json.dumps(report, indent=2))
    if len(positive_attempts) != 1 or len(positive_effects) != 1:
        raise AssertionError('independent fixture positive control failed')
    if len(native_positive) != 1 or native_positive[0]['status'] != 'cancelled':
        raise AssertionError('independent native positive control failed')
    if not all(r["status"] == "PASS" for r in report["trials"]):
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        output = Path(os.environ.get('ACCEPTANCE_ARTIFACT_DIR', 'acceptance-results/paired-live'))
        output.mkdir(parents=True, exist_ok=True)
        (output / "controller-failure.json").write_text(json.dumps({
            "status": "FAIL", "error_type": type(error).__name__,
            "frames": [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                       for f in traceback.extract_tb(error.__traceback__)[-8:]],
            "certified": False}, indent=2))
        raise SystemExit(2)
