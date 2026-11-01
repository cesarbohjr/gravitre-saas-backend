"""PR587 credential-free, on-machine acoustic cancellation experiment.

Replays retained 16 kHz WAV through the pinned Vosk acoustic model, with
real-time pacing, 20 ms audio increments, and a fail-closed negative corpus.
No LLM/STT/TTS API calls, runtime writes, or automatic promotion.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import wave

MODEL_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
RATE = 16000
FRAME_MS = 20
DEADLINE_MS = 500
RECOGNITION_TARGET_MS = 350
GRAMMAR = ["cancel", "cancel it", "abort", "stop talking", "keep working",
           "do not cancel", "don't cancel", "never mind", "can you",
           "cancer", "council", "yes", "okay", "uh huh", "[unk]"]
NEGATIVE_WORDS = ("backchannel", "baseline", "interrupt", "reconnect", "input.wav",
                  "approve", "stage", "ordinary", "speech_stop", "negation")
POSITIVE_NAMES = ("cancel-input.wav", "native/cancel.wav")
CANCEL_WORDS = {"cancel", "cancel it", "abort", "never mind"}


def expected_label(path):
    name = str(path).lower().replace("\\", "/")
    if any(name.endswith(x) for x in POSITIVE_NAMES):
        return "task_cancel"
    if any(x in name for x in NEGATIVE_WORDS):
        return "not_task_cancel"
    return "unknown"


def cancel_decision(text):
    norm = " ".join(re.findall(r"[a-z]+", text.lower()))
    # Never cancel from a substring, prefix or negated utterance.
    return norm in CANCEL_WORDS


def replay(path, model, clock=time.monotonic):
    from vosk import KaldiRecognizer
    # Archived WAVs can contain float PCM, stereo, or non-16 kHz audio.
    # Decode deterministically with local ffmpeg; never alter the source WAV.
    pcm = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(RATE), "pipe:1"],
        capture_output=True, check=True, timeout=90,
    ).stdout
    if not pcm or len(pcm) % 2:
        raise ValueError("empty_or_odd_pcm")
    recognizer = KaldiRecognizer(model, RATE, json.dumps(GRAMMAR))
    frames_per_step = RATE * FRAME_MS // 1000
    start = clock()
    total = 0
    first = None
    recognized = None
    for offset in range(0, len(pcm), frames_per_step * 2):
        data = pcm[offset:offset + frames_per_step * 2]
        total += len(data) // 2
        target = start + total / RATE
        delay = target - clock()
        if delay > 0:
            time.sleep(delay)
        if recognizer.AcceptWaveform(data):
            payload = json.loads(recognizer.Result())
            text = payload.get("text", "")
        else:
            payload = json.loads(recognizer.PartialResult())
            text = payload.get("partial", "")
        if cancel_decision(text) and first is None:
            first = round((clock() - start) * 1000, 3)
            recognized = text
    if first is None:
        text = json.loads(recognizer.FinalResult()).get("text", "")
        if cancel_decision(text):
            first = round((clock() - start) * 1000, 3)
            recognized = text
    return {"recognition_wall_ms": first, "audio_duration_ms": round(total / RATE * 1000, 3),
            "cancel_observed": first is not None, "recognized_cancel": recognized is not None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--recordings", required=True)
    parser.add_argument("--output", default="acceptance-results/local-acoustic-candidate.json")
    args = parser.parse_args()
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    model = Model(args.model)
    root = Path(args.recordings)
    wavs = sorted(root.rglob("*.wav"))
    rows = []
    for path in wavs:
        label = expected_label(path.relative_to(root))
        if label == "unknown":
            continue
        try:
            outcome = replay(path, model)
            outcome.update(fixture=str(path.relative_to(root)), expected=label,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        except Exception as exc:
            outcome = {"fixture": str(path.relative_to(root)), "expected": label,
                       "error_type": type(exc).__name__}
        rows.append(outcome)
    positives = [x for x in rows if x["expected"] == "task_cancel"]
    negatives = [x for x in rows if x["expected"] == "not_task_cancel"]
    false_cancels = [x for x in negatives if x.get("cancel_observed")]
    misses = [x for x in positives if x.get("recognition_wall_ms") is None
              or x["recognition_wall_ms"] > RECOGNITION_TARGET_MS]
    errors = [x for x in rows if "error_type" in x]
    # Require explicit spoken confusables/negations; generic baseline files do not
    # establish that a prefix like "cancel" is safe before the utterance ends.
    required_negative_classes = ("negation", "speech_stop", "backchannel")
    coverage = {label: any(label in x["fixture"].lower() for x in negatives)
                for label in required_negative_classes}
    candidate_pass = bool(positives and negatives and all(coverage.values())
                          and not false_cancels and not misses and not errors)
    result = {"status": "ACOUSTIC_CANDIDATE_PASS_NOT_RUNTIME_CERTIFIED" if candidate_pass else "BLOCKED",
              "model": "vosk-model-small-en-us-0.15", "model_archive_sha256": MODEL_SHA256,
              "configuration": {"sample_rate": RATE, "frame_ms": FRAME_MS, "grammar": GRAMMAR,
                                "decoder": "vosk==0.3.45", "input_normalizer": "ffmpeg_s16le_mono_16000"},
              "recognition_target_ms": RECOGNITION_TARGET_MS,
              "end_to_end_limit_ms": DEADLINE_MS, "certified": False, "runtime_changed": False,
              "provider_calls": 0, "e2e_write_fence_latency_ms": None,
              "physical_audio_cutoff_ms": None, "positive_count": len(positives),
              "negative_count": len(negatives), "false_cancellation_count": len(false_cancels),
              "missed_or_late_count": len(misses), "errors": len(errors), "required_negative_coverage": coverage,
              "trials": rows}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "trials"}))
    print(json.dumps({"trial_diagnostics": [{"fixture": x["fixture"], "error_type": x.get("error_type"),
              "recognition_wall_ms": x.get("recognition_wall_ms")} for x in rows]}))
    return 0 if candidate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
