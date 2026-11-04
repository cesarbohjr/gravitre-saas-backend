#!/usr/bin/env python3
"""Analyze an explicitly captured browser voice acceptance manifest.

Local-only; never uploads audio or timing data. This is diagnostic triage, not
proof of audible quality or TTS-provider causality. Input is the manifest
produced by apps/web/lib/voice-acoustic-acceptance.ts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def analyze(manifest: dict, *, audio: bytes | None = None) -> dict:
    if manifest.get("schema") != "gravitre.acoustic-acceptance.v1":
        raise ValueError("unrecognized acoustic acceptance manifest")
    rows = manifest.get("observations")
    if not isinstance(rows, list) or len(rows) > 12000:
        raise ValueError("invalid or unbounded observations")
    if manifest.get("captured_audio_kind") != "post_duck_browser_stream":
        raise ValueError("unsupported capture provenance")

    timings = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("event"), str):
            raise ValueError("invalid event")
        t = row.get("monotonic_ms")
        if not isinstance(t, (float, int)) or isinstance(t, bool) or not (0 <= t < 1e15):
            raise ValueError("invalid timestamp")
        timings.append(float(t))
    if any(b < a for a, b in zip(timings, timings[1:])):
        raise ValueError("out-of-order manifest observations")

    counts: dict[str, int] = {}
    enqueue_gaps = []
    previous_enqueue = None
    duck_started = None
    duck_intervals = []
    non_running = []
    for row, timestamp in zip(rows, timings):
        kind = row["event"]
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "pcm_enqueue":
            if previous_enqueue is not None:
                enqueue_gaps.append(round(timestamp - previous_enqueue, 2))
            previous_enqueue = timestamp
        elif kind == "duck":
            if duck_started is None:
                duck_started = timestamp
        elif kind in {"unduck", "flush"}:
            if duck_started is not None:
                duck_intervals.append(round(timestamp - duck_started, 2))
                duck_started = None
            if kind == "flush":
                previous_enqueue = None
        elif kind == "context_state" and row.get("state") != "running":
            non_running.append({"at_ms": timestamp, "state": row.get("state")})

    if duck_started is not None and timings:
        duck_intervals.append(round(timings[-1] - duck_started, 2))

    # An enqueue gap may be linguistic or transport-induced. Do not classify
    # it as starvation without simultaneous queue and worklet evidence.
    candidates = []
    if enqueue_gaps and max(enqueue_gaps) > 100:
        candidates.append("long_client_pcm_arrival_gap__cause_unverified")
    if duck_intervals and max(duck_intervals) > 250:
        candidates.append("sustained_duck__check_overlap_classification")
    if non_running:
        candidates.append("audio_context_not_running__check_browser_output")
    if counts.get("flush", 0):
        candidates.append("flush_observed__correlate_stop_or_barge_in")
    return {
        "schema": "gravitre.acoustic-triage.v1",
        "evidence_class": "browser_post_duck_capture",
        "audio_sha256": hashlib.sha256(audio).hexdigest() if audio is not None else None,
        "events": counts,
        "maximum_pcm_arrival_gap_ms": max(enqueue_gaps) if enqueue_gaps else None,
        "maximum_duck_interval_ms": max(duck_intervals) if duck_intervals else None,
        "non_running_audio_context_events": non_running[:50],
        "candidate_signatures": candidates,
        "physical_speaker_quality": "NOT_VERIFIED",
        "upstream_tts_causality": "NOT_VERIFIED",
        "independent_listening": "NOT_RUN",
        "truncated": bool(manifest.get("limits", {}).get("observations_truncated")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--audio", type=Path, help="optional corresponding local browser recording")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audio = args.audio.read_bytes() if args.audio else None
    result = analyze(json.loads(args.manifest.read_text()), audio=audio)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
