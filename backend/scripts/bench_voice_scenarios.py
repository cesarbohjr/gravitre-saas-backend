#!/usr/bin/env python3
"""Offline multi-turn voice scenario bench (no network, no vendor keys).

Drives the production Pipecat voice pipeline (``build_pipecat_voice_task``)
in-process with scripted Flux STT, a streaming fake TTS, a scripted brain and
a modelled browser, on a virtual clock. Each scenario runs N times with seeded
jitter on every delay, so a baseline and a candidate can be compared on
identical conditions.

Run from ``backend/``::

    python scripts/bench_voice_scenarios.py --runs 20 --out /tmp/bench/baseline --label baseline
    python scripts/bench_voice_scenarios.py --runs 20 --out /tmp/bench/cand --label cand \\
        --setting SOME_VOICE_FLAG=true

Writes ``results.json`` (per-run metrics + aggregates) and ``results.md``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import zlib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MODEL_NOTES = [
    "Real: every Pipecat processor between the socket and the providers, exactly as build_pipecat_voice_task wires it "
    "(utterance gate, transcript relay, speculative prefetch/generation, Flux turn strategies incl. backchannel grace "
    "window, Cognitive LLM bridge with deep ack and tool narration, interrupt reporter with stop marker and played-audio "
    "reconciliation, Pipecat TTS audio contexts and word timestamps, websocket output pacing, spoken-text tap, durable "
    "persistence and the barge-in write gate).",
    "Scripted STT follows Pipecat 1.12 Deepgram Flux frame semantics: StartOfTurn, EagerEndOfTurn/TurnResumed, "
    "EndOfTurn with finalized transcript. Flux 1.12 pushes no interim transcripts, so none are sent (as in production). "
    "Flux's own end-of-turn decision is a fixed, jittered delay after speech ends, not a model of its confidence.",
    "Fake TTS is shaped like the ElevenLabs websocket service (one context per reply, first-byte delay, faster-than-"
    "real-time streaming, flush/close). Audio is a constant tone whose sample value encodes the segment, so labels "
    "survive re-chunking. Provider-side late frames are modelled; ElevenLabs alignment quirks are not.",
    "Brain is scripted (first-token delay, streamed tokens, tool calls, failures, governed writes checked with the "
    "real raise_if_barge_in_blocks_invoke). It does not model the real CognitiveTurnKernel, model routing or tool "
    "selection; the plans are fixed per scenario.",
    "Browser model reproduces use-voice-duplex-session.ts drop rules (reply_id <= interrupted id, flush on "
    "speech.interrupted) and the voice-pcm-jitter.ts lead (120 ms initial, +60 ms per mid-reply underrun, max 320 ms). "
    "It does not model the client-side bargeIn() path (the server does not relay interim transcripts), the HTTP "
    "fallback watchdog, or AudioContext scheduling jitter.",
    "NOT modelled: acoustics, microphone echo and echo cancellation, real Deepgram/ElevenLabs/model latency "
    "distributions, network latency/jitter/loss (network_s=0), CPU load (virtual time makes processing free), "
    "multi-worker Redis stop markers (in-process fallback), and the read-only prefetch services (counted, not run).",
    "Virtual clock: asyncio timers and time.time/monotonic/perf_counter are virtual; worker threads take zero "
    "virtual time. Results are deterministic for a given seed and code version.",
]


def _git_rev() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def _quiet_logs() -> None:
    logging.disable(logging.WARNING)
    try:
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="CRITICAL")
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=20, help="runs per scenario (default 20)")
    parser.add_argument("--out", required=True, help="output directory for results.json and results.md")
    parser.add_argument("--label", default="", help="label for this result set, e.g. baseline")
    parser.add_argument("--seed", type=int, default=1000, help="seed base; run i of scenario S uses a seed derived from both")
    parser.add_argument("--scenarios", default="", help="comma-separated scenario ids (default: all)")
    parser.add_argument(
        "--setting",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Settings override applied as an environment variable before Settings load (repeatable)",
    )
    parser.add_argument("--verbose", action="store_true", help="keep application logs")
    args = parser.parse_args(argv)

    overrides: dict[str, str] = {}
    for item in args.setting:
        if "=" not in item:
            parser.error(f"--setting expects NAME=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()

    if not args.verbose:
        _quiet_logs()

    from tests.e2e.voice_scenarios.harness import build_settings, run_scenario
    from tests.e2e.voice_scenarios.metrics import aggregate, markdown_report, run_metrics
    from tests.e2e.voice_scenarios.scenarios import get_scenarios

    if not args.verbose:
        _quiet_logs()
    settings = build_settings(overrides)
    scenarios = get_scenarios([s for s in args.scenarios.split(",") if s.strip()] or None)
    started = time.time()
    results: dict[str, object] = {
        "meta": {
            "label": args.label,
            "runs": args.runs,
            "seed": args.seed,
            "git": _git_rev(),
            "overrides": overrides,
            "python": sys.version.split()[0],
        },
        "model_notes": MODEL_NOTES,
        "scenarios": {},
    }
    for scenario in scenarios:
        per_run = []
        t0 = time.time()
        for i in range(args.runs):
            seed = args.seed + i * 7919 + zlib.crc32(scenario.id.encode()) % 100_000
            res = run_scenario(scenario, seed, settings=settings)
            per_run.append(run_metrics(res))
        agg = aggregate(per_run)
        results["scenarios"][scenario.id] = {  # type: ignore[index]
            "title": scenario.title,
            "description": scenario.description,
            "expected": scenario.expected,
            "notes": scenario.notes,
            "conditions": scenario.conditions().as_dict(),
            "aggregate": agg,
            "runs": per_run,
            "wall_s": round(time.time() - t0, 2),
        }
        print(f"{scenario.id:4s} {scenario.title:45s} runs={args.runs} errors={agg['errors']} "
              f"outcomes={agg['outcomes']} wall={time.time() - t0:.1f}s", flush=True)
    results["meta"]["wall_s"] = round(time.time() - started, 1)  # type: ignore[index]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (out / "results.md").write_text(markdown_report(results))
    print(f"wrote {out / 'results.json'} and {out / 'results.md'} in {results['meta']['wall_s']} s")  # type: ignore[index]
    return 0


if __name__ == "__main__":
    os.environ.setdefault("GRAVITRE_DROP_BACKGROUND_TASKS", "1")
    raise SystemExit(main())
