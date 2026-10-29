"""Isolated real-audio adapter runner.

Invokes two separately configured *real* adapter commands with identical PCM
input. Commands must implement the documented WAV-in/WAV-out CLI contract.
This runner does not impersonate a Pipecat or LiveKit session, and never marks
a transport as operational without a successful adapter invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time

from app.services.pipecat_voice.recorded_audio_evidence import (
    certify_recorded_trials, inspect_recording,
)


def run_pair(input_wav: str, case_id: str, commands: dict[str, str], *, timeout_s: int = 120) -> dict:
    if not case_id or not isinstance(case_id, str):
        raise ValueError("case_id required")
    if not isinstance(timeout_s, int) or not 1 <= timeout_s <= 600:
        raise ValueError("invalid timeout")
    source = Path(input_wav).resolve(strict=True)
    source_evidence = inspect_recording(str(source))
    results = []
    with tempfile.TemporaryDirectory(prefix="gravitre-voice-isolated-") as tmp:
        for engine in ("pipecat", "livekit"):
            command = commands.get(engine)
            if not command or not shlex.split(command):
                raise RuntimeError(f"{engine} real adapter command not configured")
            out = Path(tmp) / (engine + ".wav")
            metrics = Path(tmp) / (engine + ".json")
            argv = [*shlex.split(command), "--input-wav", str(source),
                    "--output-wav", str(out), "--metrics-json", str(metrics)]
            started = time.monotonic_ns()
            env = {**os.environ, "GRAVITRE_VOICE_ISOLATED": "1",
                   "GRAVITRE_VOICE_ENGINE": engine}
            subprocess.run(argv, check=True, timeout=timeout_s, env=env,
                           capture_output=True)
            elapsed_ms = (time.monotonic_ns() - started) / 1_000_000
            if not out.is_file() or not metrics.is_file():
                raise RuntimeError(f"{engine} did not return audio and metrics")
            actual = inspect_recording(str(out))
            reported = json.loads(metrics.read_text())
            if reported.get("engine") != engine or reported.get("case_id") != case_id:
                raise ValueError("adapter evidence identity mismatch")
            if reported.get("input_sha256") != source_evidence["sha256"]:
                raise ValueError("adapter did not attest exact input recording")
            if reported.get("output_sha256") != actual["sha256"]:
                raise ValueError("adapter output digest mismatch")
            if reported.get("mode") != "real_transport":
                raise ValueError("mock or simulated adapter is not real-audio evidence")
            if reported.get("elapsed_ms", 0) > elapsed_ms + 5000:
                raise ValueError("reported duration exceeds measured wall time")
            row = {key: reported[key] for key in (
                "first_audio_ms", "interruption_ms", "reconnect_ms",
                "cancelled_write_executed")}
            results.append({"engine": engine, "case_id": case_id,
                            "output_sha256": actual["sha256"],
                            "input_sha256": source_evidence["sha256"],
                            "elapsed_wall_ms": elapsed_ms,
                            "output_duration_s": actual["duration_s"],
                            "metrics": row, "source": "real_adapter_process_unreviewed"})
    return {"case_id": case_id, "results": results,
            "certified": False, "human_audio_quality_review": "NOT_RUN",
            "runtime_governance_review": "NOT_RUN"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-wav", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--pipecat-command", required=True)
    parser.add_argument("--livekit-command", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    result = run_pair(args.input_wav, args.case_id,
                      {"pipecat": args.pipecat_command,
                       "livekit": args.livekit_command})
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
