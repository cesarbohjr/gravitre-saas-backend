"""Recorded-audio comparison evidence gate; no synthetic voice certification.

This module deliberately does not claim to operate Pipecat or LiveKit. A runner
must provide measured, externally collected trial records for both adapters.
"""
from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path


ENGINES = ("pipecat", "livekit")
REQUIRED = ("first_audio_ms", "interruption_ms", "reconnect_ms",
            "cancelled_write_executed", "output_wav", "recording_sha256")


def inspect_recording(path: str) -> dict:
    """Validate actual PCM WAV bytes rather than a filename or claimed duration."""
    p = Path(path)
    data = p.read_bytes()
    with wave.open(str(p), "rb") as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        compression = audio.getcomptype()
    if not frames or not rate or channels not in (1, 2) or width not in (1, 2, 3, 4) or compression != "NONE":
        raise ValueError("invalid PCM recording")
    return {"sha256": hashlib.sha256(data).hexdigest(), "duration_s": frames / rate,
            "sample_rate": rate, "channels": channels, "sample_width": width}


def certify_recorded_trials(trials: list[dict], *, minimum_pairs: int = 20) -> dict:
    """Fail closed unless both engines produced paired, measured WAV evidence.

    Human-rated quality remains a separate mandatory gate; no engine is selected.
    """
    if type(minimum_pairs) is not int or minimum_pairs < 1:
        raise ValueError("invalid minimum_pairs")
    seen: set[tuple[str, str]] = set()
    pairs: dict[str, set[str]] = {}
    summaries: dict[str, list[dict]] = {engine: [] for engine in ENGINES}
    for row in trials:
        if not isinstance(row, dict) or any(k not in row for k in ("engine", "case_id", *REQUIRED)):
            raise ValueError("missing recorded trial fields")
        engine, case_id = row["engine"], row["case_id"]
        if engine not in ENGINES or not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("invalid engine or case")
        if (engine, case_id) in seen:
            raise ValueError("duplicate engine/case")
        seen.add((engine, case_id))
        pairs.setdefault(case_id, set()).add(engine)
        for field in ("first_audio_ms", "interruption_ms", "reconnect_ms"):
            value = row[field]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid measured {field}")
        if type(row["cancelled_write_executed"]) is not bool:
            raise ValueError("invalid cancelled write flag")
        evidence = inspect_recording(row["output_wav"])
        if evidence["sha256"] != row["recording_sha256"]:
            raise ValueError("recording integrity mismatch")
        summaries[engine].append({**evidence, "case_id": case_id,
                                  "first_audio_ms": row["first_audio_ms"],
                                  "interruption_ms": row["interruption_ms"],
                                  "reconnect_ms": row["reconnect_ms"],
                                  "cancelled_write_executed": row["cancelled_write_executed"]})
    paired = sorted(case for case, engines in pairs.items() if engines == set(ENGINES))
    safety = all(not r["cancelled_write_executed"] for rows in summaries.values() for r in rows)
    sufficient = len(paired) >= minimum_pairs and all(len(summaries[e]) == len(paired) for e in ENGINES)
    return {"paired_cases": len(paired), "recorded_evidence_sufficient": sufficient,
            "cancelled_write_safety_passed": safety, "quality_review": "NOT_RUN",
            "certified": False, "adapter_selected": None,
            "reason": "Independent listening, functional transport, and authorization review required",
            "trials": summaries}


if __name__ == "__main__":
    import sys
    rows = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(certify_recorded_trials(rows), sort_keys=True))
