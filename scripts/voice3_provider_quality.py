"""Isolated paired provider audio checks. No live runtime configuration changes."""
import hashlib
import io
import re
import time
import wave

from voice3_acoustic_eval import analyze_pcm, compare, integrity_failures, word_error_rate, RATE

FIXTURES = (
    ("professional", "The review is ready. We can discuss the next steps."),
    ("warm", "That sounds difficult. Take your time, and we can work through it."),
    ("enthusiastic", "Wonderful news! That is a milestone worth celebrating."),
)
MAX_BYTES = RATE * 2 * 30
MODELS = {"flash": "eleven_flash_v2_5", "dialogue": "eleven_v3"}


def synthesize(client, key, voice_id, protocol, text):
    if not re.fullmatch(r"[A-Za-z0-9]{16,64}", voice_id):
        raise ValueError("invalid voice ID")
    model = MODELS[protocol]
    if protocol == "dialogue":
        url = "https://api.elevenlabs.io/v1/text-to-dialogue"
        body = {"inputs": [{"text": text, "voice_id": voice_id}], "model_id": model,
                "settings": {"stability": 0.5}}
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        body = {"text": text, "model_id": model}
    started = time.monotonic()
    chunks = bytearray()
    first_ms = None
    with client.stream("POST", url, params={"output_format": "pcm_16000"},
                       headers={"xi-api-key": key, "Accept": "application/octet-stream"},
                       json=body) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in {"audio/pcm", "audio/basic", "application/octet-stream", "audio/l16"}:
            raise ValueError("unexpected audio format")
        for chunk in response.iter_bytes():
            if not chunk:
                continue
            if first_ms is None:
                first_ms = round((time.monotonic()-started)*1000)
            if len(chunks)+len(chunk)>MAX_BYTES:
                raise ValueError("oversized PCM")
            chunks.extend(chunk)
    pcm = bytes(chunks)
    metrics = analyze_pcm(pcm)
    return pcm, {"voice_id": voice_id, "model": model, "protocol": protocol,
                 "first_response_bytes_ms": first_ms,
                 "total_http_ms": round((time.monotonic()-started)*1000),
                 "audio_sha256": hashlib.sha256(pcm).hexdigest(),
                 "metrics": metrics, "integrity_failures": integrity_failures(metrics)}


def transcribe(client, key, pcm, reference):
    # WAV container explicitly declares the same mono PCM16 sample rate.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm)
    response = client.post("https://api.deepgram.com/v1/listen",
                           params={"model": "nova-3", "language": "en"},
                           headers={"Authorization": "Token " + key, "Content-Type": "audio/wav"},
                           content=buf.getvalue())
    response.raise_for_status()
    text = response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
    return word_error_rate(reference, text)


def evaluate_pair(client, env, old_id, candidate_id, cache=None):
    cache = {} if cache is None else cache
    result = {"fixtures": [], "gates": {}}
    if not candidate_id:
        return result
    for fixture, text in FIXTURES:
        row = {"fixture": fixture}
        for label, voice, protocol in (("baseline", old_id, "flash"),
                                       ("candidate_flash", candidate_id, "flash"),
                                       ("candidate_dialogue", candidate_id, "dialogue")):
            try:
                k = (voice, protocol, fixture)
                if k not in cache:
                    pcm, metrics = synthesize(client, env["ELEVENLABS_API_KEY"], voice, protocol, text)
                    if env.get("DEEPGRAM_API_KEY"):
                        try:
                            metrics["wer"] = transcribe(client, env["DEEPGRAM_API_KEY"], pcm, text)
                        except Exception as exc:
                            metrics["stt_error_type"] = type(exc).__name__
                    cache[k] = metrics
                row[label] = cache[k]
            except Exception as exc:
                row[label] = {"error_type": type(exc).__name__}
        for label in ("candidate_flash", "candidate_dialogue"):
            base, candidate = row["baseline"], row[label]
            if "metrics" in base and "metrics" in candidate:
                row[label+"_comparison"] = compare(base["metrics"], candidate["metrics"])
        result["fixtures"].append(row)
    rows = result["fixtures"]
    def clean(label):
        return all("metrics" in row[label] and row[label].get("integrity_failures") == [] for row in rows)
    for gate,label in (("flash_http","candidate_flash"),("v3_dialogue","candidate_dialogue")):
        result["gates"][gate] = "PASS" if clean(label) else "FAIL"
    result["gates"]["acoustic_integrity"] = "PASS" if clean("candidate_flash") and clean("candidate_dialogue") else "FAIL"
    # Preliminary screen only; the comparative quality and human prosody gates
    # deliberately remain unresolved until calibrated acceptance is available.
    errors = [row[label].get("wer") for row in rows for label in ("candidate_flash","candidate_dialogue")]
    baseline_errors = [row["baseline"].get("wer") for row in rows]
    if all(isinstance(v,(int,float)) for v in errors+baseline_errors):
        result["gates"]["intelligibility"] = "PASS" if all(v <= 0.20 for v in errors) else "FAIL"
    else:
        result["gates"]["intelligibility"] = "NOT RUN"
    result["gates"]["paired_quality"] = "NOT RUN"
    return result
