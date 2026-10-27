#!/usr/bin/env python3
"""Measure actual recorded voice output, not scheduled buffer estimates.

Usage:
 python scripts/measure-voice-audio-acceptance.py --manifest evidence.json --out results.json

Manifest: {"recordings":[{"profile":"light","wav":"light.wav",
  "tts_request_ms":0,"first_audio_ms":180,"interruption_requested_ms":2000,
  "audio_stopped_ms":2070}, ...]}
Timestamps must come from the same monotonic capture clock. WAV must be
uncompressed mono/stereo PCM 16-bit. Report-only: no invented pass/fail.
"""
from __future__ import annotations

import argparse
import json
import statistics
import struct
import wave
from pathlib import Path


def analyze_wav(path: Path, *, silence_dbfs: float = -42.0, min_gap_ms: float = 35.0) -> dict:
    with wave.open(str(path), "rb") as audio:
        rate = audio.getframerate()
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        frames = audio.getnframes()
        if width != 2 or channels not in (1, 2):
            raise ValueError("Expected 16-bit mono/stereo PCM WAV")
        raw = audio.readframes(frames)
    if rate <= 0:
        raise ValueError("Invalid sample rate")
    # 10 ms RMS windows are robust to zero crossings and brief consonant pauses.
    window = max(1, round(rate / 100))
    samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
    threshold = 32768.0 * 10 ** (silence_dbfs / 20)
    active = []
    for start in range(0, frames, window):
        end = min(frames, start + window)
        power = sum(
            sum(samples[i * channels + c] ** 2 for c in range(channels)) / channels
            for i in range(start, end)
        ) / max(1, end - start)
        active.append(power ** 0.5 > threshold)
    first = next((i for i, flag in enumerate(active) if flag), None)
    last = next((i for i in range(len(active) - 1, -1, -1) if active[i]), None)
    gaps = []
    if first is not None and last is not None:
        start = None
        for i in range(first, last + 1):
            if not active[i] and start is None:
                start = i
            if active[i] and start is not None:
                gap = (i - start) * window * 1000 / rate
                if gap >= min_gap_ms:
                    gaps.append(round(gap, 1))
                start = None
    return {
        "duration_ms": round(frames * 1000 / rate, 1),
        "sample_rate": rate,
        "internal_silence_gaps_ms": gaps,
        "longest_internal_gap_ms": max(gaps, default=0),
        "gap_count": len(gaps),
        "note": "Internal silences include intentional linguistic pauses; segment-boundary attribution requires timestamps.",
    }


def analyze_manifest(manifest: dict, base: Path) -> dict:
    rows = []
    for item in manifest.get("recordings", []):
        path = (base / item["wav"]).resolve()
        if not path.is_relative_to(base.resolve()):
            raise ValueError("WAV path escapes manifest directory")
        result = {"profile": item["profile"], "wav": str(path), **analyze_wav(path)}
        if "tts_request_ms" in item and "first_audio_ms" in item:
            result["tts_first_audio_latency_ms"] = round(
                item["first_audio_ms"] - item["tts_request_ms"], 1
            )
        if "interruption_requested_ms" in item and "audio_stopped_ms" in item:
            result["interruption_stop_latency_ms"] = round(
                item["audio_stopped_ms"] - item["interruption_requested_ms"], 1
            )
        rows.append(result)
    grouped = {}
    for row in rows:
        grouped.setdefault(row["profile"], []).append(row)
    return {
        "recordings": rows,
        "profiles": {
            name: {
                "count": len(items),
                "median_longest_gap_ms": statistics.median(x["longest_internal_gap_ms"] for x in items),
                "median_tts_first_audio_ms": statistics.median(
                    x["tts_first_audio_latency_ms"] for x in items if "tts_first_audio_latency_ms" in x
                ) if any("tts_first_audio_latency_ms" in x for x in items) else None,
                "median_interruption_stop_ms": statistics.median(
                    x["interruption_stop_latency_ms"] for x in items if "interruption_stop_latency_ms" in x
                ) if any("interruption_stop_latency_ms" in x for x in items) else None,
            }
            for name, items in grouped.items()
        },
        "limitations": [
            "Recorded WAV required; no synthetic results substituted.",
            "Silence is not proof of a playback discontinuity.",
            "Per-segment boundary markers and listening review required for gap attribution.",
            "Timestamps must use the same monotonic clock.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    result = analyze_manifest(manifest, args.manifest.parent)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["profiles"], indent=2))


if __name__ == "__main__":
    main()
