#!/usr/bin/env python3
"""Offline multi-turn voice scenario bench (no network, no vendor keys).

Drives the production Pipecat voice pipeline (``build_pipecat_voice_task``)
in-process with scripted Flux STT, a streaming fake TTS, a scripted brain and
a modelled browser, on a virtual clock. Each scenario runs N times with seeded
jitter on every delay, so a baseline and a candidate can be compared on
identical conditions.

Run from ``backend/``::

    python scripts/bench_voice_scenarios.py --runs 20 --out /tmp/bench/baseline --label baseline
    python scripts/bench_voice_scenarios.py --runs 20 --out /tmp/bench/prod --profile production_inferred
    python scripts/bench_voice_scenarios.py --runs 20 --out /tmp/bench/cand --label cand \\
        --profile defaults --setting SOME_VOICE_FLAG=true

``--profile`` loads a flag set from ``scripts/bench_profiles/<name>.json`` (or a
path) and clears every other VOICE_* variable inherited from the shell, so a
result depends only on the revision, the profile, the seed and N. ``--setting``
overrides apply on top of the profile.

Writes ``results.json`` (per-run metrics + aggregates, seeds, conditions,
resolved flags) and ``results.md``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
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


PROFILE_DIR = Path(__file__).resolve().parent / "bench_profiles"


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=BACKEND_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return None


def _git_rev() -> str | None:
    return _git("rev-parse", "--short", "HEAD")


def _git_meta() -> dict[str, object]:
    """Revision, whether the tree had local edits, and the backend/app tree
    hash (two runs with the same hash ran the same product code)."""
    dirty = _git("status", "--porcelain", "--", "app")
    return {
        "git": _git_rev(),
        "app_tree": _git("rev-parse", "HEAD:backend/app"),
        "app_dirty": bool(dirty) if dirty is not None else None,
    }


def load_profile(name_or_path: str) -> dict[str, object]:
    path = Path(name_or_path)
    if not path.suffix:
        path = PROFILE_DIR / f"{name_or_path}.json"
    profile = json.loads(path.read_text())
    if not isinstance(profile.get("settings"), dict):
        raise TypeError(f"profile {path} has no 'settings' object")
    profile.setdefault("name", path.stem)
    profile["path"] = str(path.relative_to(BACKEND_ROOT)) if path.is_relative_to(BACKEND_ROOT) else str(path)
    return profile


def apply_profile(profile: dict[str, object] | None, overrides: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Settings for this run: the profile's, then ``overrides``. With a profile,
    every other VOICE_* variable inherited from the shell is cleared so the
    result does not depend on the caller's environment. Returns (settings,
    cleared variable names)."""
    merged: dict[str, str] = {}
    cleared: list[str] = []
    if profile is not None:
        merged.update({str(k).upper(): str(v) for k, v in dict(profile["settings"]).items()})  # type: ignore[arg-type]
    merged.update({k.upper(): v for k, v in overrides.items()})
    if profile is not None:
        for key in sorted(os.environ):
            if key.upper().startswith("VOICE_") and key.upper() not in merged:
                cleared.append(key)
                os.environ.pop(key, None)
    return merged, cleared


def _effective(settings: object) -> tuple[dict[str, bool], dict[str, object]]:
    try:
        from app.services.pipecat_voice.voice_latency_tuning import (
            effective_voice_flags,
            effective_voice_settings,
        )
    except Exception:  # noqa: BLE001 - older revisions
        return {}, {}
    return effective_voice_flags(settings), effective_voice_settings(settings)


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
    parser.add_argument(
        "--profile",
        default="",
        help="flag profile: a name in scripts/bench_profiles (production_inferred, defaults) or a JSON path",
    )
    parser.add_argument("--verbose", action="store_true", help="keep application logs")
    args = parser.parse_args(argv)

    overrides: dict[str, str] = {}
    for item in args.setting:
        if "=" not in item:
            parser.error(f"--setting expects NAME=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        overrides[key.strip()] = value.strip()
    profile = load_profile(args.profile) if args.profile else None
    applied, cleared = apply_profile(profile, overrides)

    if not args.verbose:
        _quiet_logs()

    from tests.e2e.voice_scenarios.harness import build_settings, run_scenario
    from tests.e2e.voice_scenarios.metrics import (
        aggregate,
        markdown_report,
        run_metrics,
    )
    from tests.e2e.voice_scenarios.scenarios import get_scenarios

    if not args.verbose:
        _quiet_logs()
    settings = build_settings(applied)
    flags, tuned = _effective(settings)
    scenarios = get_scenarios([s for s in args.scenarios.split(",") if s.strip()] or None)
    started = time.time()
    results: dict[str, object] = {
        "meta": {
            "label": args.label or (profile or {}).get("name", ""),
            "runs": args.runs,
            "seed": args.seed,
            "seed_rule": "run i of scenario S uses seed + i*7919 + crc32(S) % 100000",
            **_git_meta(),
            "profile": {k: v for k, v in (profile or {}).items() if k != "settings"} or None,
            "overrides": applied,
            "cleared_env": cleared,
            "effective_flags": flags,
            "effective_settings": tuned,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
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
            "pass_outcomes": list(getattr(scenario, "pass_outcomes", ()) or ()),
            "graded": any(r.get("passed") is not None for r in per_run),
            "conditions": scenario.conditions().as_dict(),
            "aggregate": agg,
            "runs": per_run,
            "wall_s": round(time.time() - t0, 2),
        }
        acc = agg.get("accuracy") or {}
        print(f"{scenario.id:4s} {scenario.title:45s} runs={args.runs} errors={agg['errors']} "
              f"pass={acc.get('pass')}/{acc.get('n')} outcomes={agg['outcomes']} wall={time.time() - t0:.1f}s", flush=True)
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
