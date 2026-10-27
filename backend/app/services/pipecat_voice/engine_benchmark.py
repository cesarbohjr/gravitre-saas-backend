"""Phase 2 voice-engine evaluation contract.

Transport selection never changes One Brain, approval, tenant, or tool execution.
Only sanitized aggregate measurements are accepted; no audio or transcript data.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Literal

Engine = Literal["duplex", "pipecat"]


@dataclass(frozen=True)
class VoiceTrial:
    engine: Engine
    first_audio_ms: float
    audio_gap_ms: float
    interruption_ms: float
    completed: bool
    cost_usd: float
    cancelled_write_executed: bool = False

    def __post_init__(self) -> None:
        if self.engine not in ("duplex", "pipecat"):
            raise ValueError("unsupported engine")
        for name in ("first_audio_ms", "audio_gap_ms", "interruption_ms", "cost_usd"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not (0 <= value < float("inf")):
                raise ValueError(f"invalid {name}")


def compare_engines(trials: list[VoiceTrial], *, minimum_per_engine: int = 20) -> dict:
    """Fail closed: Pipecat is never recommended without comparable live evidence."""
    if minimum_per_engine < 1:
        raise ValueError("minimum_per_engine must be positive")
    groups = {engine: [t for t in trials if t.engine == engine] for engine in ("duplex", "pipecat")}
    summary = {}
    for engine, rows in groups.items():
        summary[engine] = {
            "count": len(rows),
            "completion_rate": sum(t.completed for t in rows) / len(rows) if rows else None,
            "first_audio_p50_ms": median(t.first_audio_ms for t in rows) if rows else None,
            "audio_gap_p50_ms": median(t.audio_gap_ms for t in rows) if rows else None,
            "interruption_p50_ms": median(t.interruption_ms for t in rows) if rows else None,
            "cost_p50_usd": median(t.cost_usd for t in rows) if rows else None,
            "cancelled_write_violations": sum(t.cancelled_write_executed for t in rows),
        }
    eligible = all(len(rows) >= minimum_per_engine for rows in groups.values())
    safe = all(not t.cancelled_write_executed for t in trials)
    baseline, candidate = summary["duplex"], summary["pipecat"]
    # Conservative adoption: no safety regressions; reliability cannot fall,
    # and median latency/gap/interruption/cost cannot worsen.
    adopt = bool(eligible and safe
        and candidate["completion_rate"] >= baseline["completion_rate"]
        and all(candidate[key] <= baseline[key] for key in (
            "first_audio_p50_ms", "audio_gap_p50_ms",
            "interruption_p50_ms", "cost_p50_usd"
        )))
    return {"engines": summary, "evidence_sufficient": eligible,
            "safety_passed": safe, "recommend_pipecat": adopt,
            "default_engine": "duplex"}
