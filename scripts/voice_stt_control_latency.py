"""Bounded provider-only timing experiment; never a voice certification verdict.

Stream the unchanged paired cancellation/backchannel recordings in real time to
Flux, Nova-3 and optionally ElevenLabs Scribe Realtime. Export timing and fixed classifications, never transcripts,
credentials, provider bodies, or account identifiers. No tenant/API/TTS writes.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode
import wave

FIXTURES = {
    "cancel": ("cancel-input.wav", "cb59c58a686767cc7fc882ac6773dbd09beed5c22d420a229524f8a55a2c4936"),
    "backchannel": ("backchannel-input.wav", "91e37080c6122a0e5df30858e72bffcbeb34e4a4415597771f7fa78382bb2133"),
    "ordinary_request": ("input.wav", "bd1062d37671b640cf0be2ae4397d3c133bd23131ac2d6f568c1ec1c076e3731"),
}

# Product control vocabulary, fixed before measurement; never fixture text.
# Research-only: recognition bias is not cancellation/approval authority.
CONTROL_KEYTERMS = ("cancel", "abort", "stop", "pause", "wait")


def fixture(directory, case):
    name, digest = FIXTURES[case]
    with wave.open(str(directory / name)) as recording:
        if (recording.getnchannels(), recording.getsampwidth(), recording.getframerate()) != (1, 2, 16000):
            raise ValueError("unexpected_recording_format")
        pcm = recording.readframes(recording.getnframes())
    if not 3200 < len(pcm) < 320000 or hashlib.sha256(pcm).hexdigest() != digest:
        raise ValueError("recording_digest_mismatch")
    return pcm


def observation(message, model):
    """Normalize only documented event shapes; no provider text is exported."""
    speech_start = False
    text = ""
    if model in {"flux", "flux_controls"} and message.get("type") == "TurnInfo":
        speech_start = message.get("event") == "StartOfTurn"
        text = message.get("transcript", "")
    elif model == "nova3":
        speech_start = message.get("type") == "SpeechStarted"
        if message.get("type") == "Results":
            alternatives = message.get("channel", {}).get("alternatives", [])
            if alternatives:
                text = alternatives[0].get("transcript", "")
    elif model == "scribe" and message.get("message_type") in {"partial_transcript", "committed_transcript"}:
        text = message.get("text", "")
    if not isinstance(text, str):
        text = ""
    words = re.findall(r"[a-z']+", text.lower())
    # Diagnostic only, deliberately not a runtime intent or authorization gate.
    stop_word = bool(set(words) & {"cancel", "stop", "pause"})
    return speech_start, bool(words), stop_word


def connection_config(key, model):
    if model == "scribe":
        # Official Realtime API, no keyword bias or transcript editing.
        # https://elevenlabs.io/docs/api-reference/speech-to-text/v-1-speech-to-text-realtime
        params = dict(model_id="scribe_v2_realtime", audio_format="pcm_16000",
                      language_code="en", commit_strategy="manual")
        return ("wss://api.elevenlabs.io/v1/speech-to-text/realtime?" + urlencode(params),
                {"xi-api-key": key})
    if model not in {"flux", "flux_controls", "nova3"}:
        raise ValueError("unsupported_model")
    is_flux = model in {"flux", "flux_controls"}
    params = dict(model="flux-general-en" if is_flux else "nova-3-general",
                  encoding="linear16", sample_rate=16000)
    if model == "flux_controls":
        params["keyterm"] = CONTROL_KEYTERMS
    if model == "nova3":
        params.update(interim_results="true", vad_events="true", language="en")
    return ("wss://api.deepgram.com/" + ("v2" if is_flux else "v1") + "/listen?" + urlencode(params, doseq=True),
            {"Authorization": "Token " + key})


def audio_message(pcm, model):
    if model == "scribe":
        return json.dumps(dict(message_type="input_audio_chunk",
            audio_base_64=base64.b64encode(pcm).decode("ascii"), sample_rate=16000, commit=False))
    return pcm


async def trial(key, model, case, pcm, repetition):
    from websockets.asyncio.client import connect

    url, headers = connection_config(key, model)
    row = dict(model=model, case=case, repetition=repetition,
               pcm_sha256=hashlib.sha256(pcm).hexdigest(), status="NOT RUN",
               first_speech_start_ms=None, first_transcript_ms=None,
               first_stop_word_ms=None, max_send_lateness_ms=0)
    try:
        async with asyncio.timeout(20):
            async with connect(url, additional_headers=headers,
                               open_timeout=5, close_timeout=2, max_size=262144) as ws:
                loop = asyncio.get_running_loop()
                input_start = None
                ready = asyncio.Event()
                if model != "scribe":
                    ready.set()

                async def receive():
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            continue
                        data = json.loads(raw)
                        if data.get("message_type") == "session_started":
                            ready.set()
                        if data.get("type") == "Error" or data.get("error") or data.get("message_type") in {
                            "auth_error", "quota_exceeded", "rate_limited", "unaccepted_terms",
                            "throttled", "input_error", "queue_overflow", "resource_exhausted",
                        }:
                            raise RuntimeError("provider_error")
                        if input_start is None:
                            continue
                        elapsed = (loop.time() - input_start) * 1000
                        for field, seen in zip(("first_speech_start_ms", "first_transcript_ms", "first_stop_word_ms"),
                                               observation(data, model)):
                            if seen and row[field] is None:
                                row[field] = round(elapsed, 3)

                receiver = asyncio.create_task(receive())
                try:
                    await asyncio.wait_for(ready.wait(), timeout=5)
                    # Keep the socket warm with one second of silence before
                    # measurement, like the existing ongoing paired session.
                    audio = bytes(32000) + pcm + bytes(32000 * 3)
                    started = loop.time()
                    for offset in range(0, len(audio), 640):
                        await asyncio.sleep(max(0, started + offset / 32000 - loop.time()))
                        if offset == 32000:
                            input_start = loop.time()
                        if input_start is not None:
                            row["max_send_lateness_ms"] = round(max(row["max_send_lateness_ms"],
                                (loop.time() - started - offset / 32000) * 1000), 3)
                        await ws.send(audio_message(audio[offset:offset + 640], model))
                        if receiver.done():
                            await receiver
                            raise RuntimeError("provider_closed_early")
                    await asyncio.sleep(.2)
                    if receiver.done():
                        await receiver
                        raise RuntimeError("provider_closed_early")
                    row["status"] = "OBSERVED" if row["first_transcript_ms"] is not None else "NO_TRANSCRIPT"
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
    except Exception:
        # Exception text may contain headers or raw provider response bodies.
        row["status"] = "TRANSPORT_OR_PROVIDER_ERROR"
    return row


def write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


async def run(directory, key, source_sha, scribe_key=None, *, flux_control_comparison=False, output=None):
    # Verify every digest before any connection or provider spend.
    recordings = {case: fixture(directory, case) for case in FIXTURES}
    report = dict(source_sha=source_sha, status="RUNNING", certified=False,
                  scope="provider_only_control_word_latency", cutoff_reference="recording_input_start",
                  runtime_changed=False, trials=[])
    if flux_control_comparison:
        report["experimental_configuration"] = dict(
            keyterms=list(CONTROL_KEYTERMS), provider_word_target_ms=400,
            runtime_cutoff_limit_ms=500, negative_stop_words_allowed=0,
            selection="NOT SELECTED; requires broader confusable/negation and real runtime tests",
        )
    if output is not None:
        write_report(output, report)
    for repetition in range(1, 4):
        for case, pcm in recordings.items():
            # Alternate first model to avoid always giving one model a colder
            # network slot. No retries, best-of selection or discarded failures.
            models = ("flux", "nova3") if repetition % 2 else ("nova3", "flux")
            if flux_control_comparison:
                models = ("flux", "flux_controls") if repetition % 2 else ("flux_controls", "flux")
            elif scribe_key:
                models = models + ("scribe",) if repetition % 2 else ("scribe",) + models
            for model in models:
                report["trials"].append(await trial(scribe_key if model == "scribe" else key,
                                                   model, case, pcm, repetition))
                if output is not None:
                    write_report(output, report)
    report["status"] = "OBSERVED" if all(r["status"] == "OBSERVED" for r in report["trials"]) else "INCOMPLETE"
    if output is not None:
        write_report(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flux-control-comparison", action="store_true")
    args = parser.parse_args()
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        raise SystemExit("missing_acceptance_deepgram_key")
    report = asyncio.run(run(args.recordings, key, os.environ.get("ACCEPTANCE_SOURCE_SHA", ""),
                            os.environ.get("ELEVENLABS_API_KEY"),
                            flux_control_comparison=args.flux_control_comparison, output=args.output))
    print(json.dumps(report))
    return 0 if report["status"] == "OBSERVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
