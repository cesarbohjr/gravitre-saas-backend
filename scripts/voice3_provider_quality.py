"""Isolated paired provider audio checks. No live runtime configuration changes."""
import hashlib
import io
import math
import statistics
import re
import time
import wave

from voice3_acoustic_eval import analyze_pcm, compare, integrity_failures, word_error_rate, RATE

FIXTURES = (
    ("professional", "The review is ready. We can discuss the next steps."),
    ("warm", "That sounds difficult. Take your time, and we can work through it."),
    ("enthusiastic", "Wonderful news! That is a milestone worth celebrating."),
    ("casual", "Sure, that works for me. What would you like to try next?"),
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


# Provisional diagnostic envelope: three independent baseline takes, robust
# median and observed range with measurement-resolution floors. This is not
# a statistically validated speaker similarity or emotional quality score.
BASELINE_TAKES = 3
FEATURE_FLOORS = {"pitch_median_hz": 5.0, "pitch_iqr_hz": 5.0,
                  "duration_ms": 100.0, "max_internal_pause_ms": 40.0}
MAX_WER = 0.20
MAX_WER_DELTA = 0.0  # No aggregate regression against baseline median.

def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

def acoustic_envelope(baselines, candidate):
    if len(baselines) != BASELINE_TAKES:
        return {"status": "NOT RUN", "features": {}}
    features = {}
    for name, floor in FEATURE_FLOORS.items():
        values = [b.get(name) for b in baselines]
        actual = candidate.get(name)
        if not all(finite(v) for v in values + [actual]):
            return {"status": "NOT RUN", "features": features}
        center = statistics.median(values)
        scale = max(floor, max(abs(v-center) for v in values))
        features[name] = {"baseline_median": center, "baseline_range": [min(values),max(values)],
                          "candidate": actual, "normalized_deviation": abs(actual-center)/scale}
    return {"status": "OUTSIDE_OBSERVED_ENVELOPE" if any(
        f["normalized_deviation"] > 1 for f in features.values()) else "WITHIN_OBSERVED_ENVELOPE",
        "features": features, "identity_similarity": "NOT ESTABLISHED"}

def comparative_wer(rows, label):
    base = []
    candidate = []
    for row in rows:
        takes = row.get("baseline_takes", [])
        values = [x.get("wer") for x in takes]
        value = row.get(label, {}).get("wer")
        if len(values) != BASELINE_TAKES or not all(finite(v) and v >= 0 for v in values+[value]):
            return {"status": "NOT RUN"}
        base.append(statistics.median(values))
        candidate.append(value)
    if not base:
        return {"status": "NOT RUN"}
    delta = statistics.fmean(candidate)-statistics.fmean(base)
    return {"status": "PASS" if max(candidate) <= MAX_WER and delta <= MAX_WER_DELTA+1e-9
            and all(c <= b+1e-9 for b,c in zip(base,candidate)) else "FAIL",
            "baseline_mean_wer": statistics.fmean(base), "candidate_mean_wer": statistics.fmean(candidate),
            "delta_wer": delta, "per_fixture_delta": [c-b for b,c in zip(base,candidate)]}

def evaluate_pair(client, env, old_id, candidate_id, cache=None):
    cache = {} if cache is None else cache
    result = {"fixtures": [], "gates": {}}
    if not candidate_id:
        return result
    for fixture, text in FIXTURES:
        row = {"fixture": fixture}
        jobs = [(f"baseline_{i}", old_id, "flash", i) for i in range(BASELINE_TAKES)]
        jobs += [("candidate_flash", candidate_id, "flash", BASELINE_TAKES),
                 ("candidate_dialogue", candidate_id, "dialogue", BASELINE_TAKES)]
        for label, voice, protocol, take in jobs:
            try:
                k = (voice, protocol, fixture, take)
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
        row["baseline_takes"] = [row.pop(f"baseline_{i}") for i in range(BASELINE_TAKES)]
        row["baseline"] = row["baseline_takes"][0]
        for label in ("candidate_flash", "candidate_dialogue"):
            base, candidate = row["baseline"], row[label]
            if all(t.get("integrity_failures") == [] for t in row["baseline_takes"]) and candidate.get("integrity_failures") == []:
                row[label+"_envelope"] = acoustic_envelope(
                    [t["metrics"] for t in row["baseline_takes"]], candidate["metrics"])
            if "metrics" in base and "metrics" in candidate:
                row[label+"_comparison"] = compare(base["metrics"], candidate["metrics"])
        result["fixtures"].append(row)
    rows = result["fixtures"]
    def clean(label):
        return all("metrics" in row[label] and row[label].get("integrity_failures") == [] for row in rows)
    for gate,label in (("flash_http","candidate_flash"),("v3_dialogue","candidate_dialogue")):
        result["gates"][gate] = "PASS" if clean(label) else "FAIL"
    result["gates"]["acoustic_integrity"] = "PASS" if clean("candidate_flash") and clean("candidate_dialogue") else "FAIL"
    result["comparative_intelligibility"] = {label: comparative_wer(rows,label)
        for label in ("candidate_flash","candidate_dialogue")}
    statuses = [x["status"] for x in result["comparative_intelligibility"].values()]
    result["gates"]["intelligibility"] = "FAIL" if "FAIL" in statuses else (
        "PASS" if all(s == "PASS" for s in statuses) else "NOT RUN")
    result["subjective_review"] = {"status": "NOT RUN", "dimensions": [
        "naturalness", "emotion appropriateness", "warmth", "emphasis", "identity continuity"],
        "method": "blinded paired listening; no acoustic proxy can pass this gate"}
    result["gates"]["paired_quality"] = "NOT RUN"
    result["gates"]["prosody_review"] = "NOT RUN"
    return result
