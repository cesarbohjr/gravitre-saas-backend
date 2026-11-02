"""Phase 2 voice-engine evaluation contract.

Transport selection never changes One Brain, approval, tenant, or tool execution.
Only sanitized aggregate measurements are accepted; no audio or transcript data.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Literal

Engine = Literal["duplex", "pipecat", "livekit"]


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
        if self.engine not in ("duplex", "pipecat", "livekit"):
            raise ValueError("unsupported engine")
        for name in ("completed", "cancelled_write_executed"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"invalid {name}")
        for name in ("first_audio_ms", "audio_gap_ms", "interruption_ms", "cost_usd"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not (0 <= value < float("inf")):
                raise ValueError(f"invalid {name}")


def compare_engines(trials: list[VoiceTrial], *, minimum_per_engine: int = 20) -> dict:
    """Descriptive aggregates only; they cannot prove live evidence or adoption.

    These rows have no task pairing, recording integrity, source/environment
    provenance or independently reviewed quality. Even favorable metrics cannot
    satisfy the mandatory pre-merge voice framework gate.
    """
    if type(minimum_per_engine) is not int or minimum_per_engine < 1:
        raise ValueError("minimum_per_engine must be positive")
    if any(not isinstance(t, VoiceTrial) for t in trials):
        raise ValueError("VoiceTrial rows required")
    groups = {engine: [t for t in trials if t.engine == engine] for engine in ("duplex", "pipecat", "livekit")}
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
    counts_sufficient = all(len(rows) >= minimum_per_engine for rows in groups.values())
    safe = all(not t.cancelled_write_executed for t in trials)
    baseline = summary["duplex"]
    keys = ("first_audio_p50_ms", "audio_gap_p50_ms", "interruption_p50_ms", "cost_p50_usd")
    diagnostics = {}
    for engine in ("pipecat", "livekit"):
        candidate = summary[engine]
        diagnostics[engine] = bool(counts_sufficient and safe
            and candidate["completion_rate"] >= baseline["completion_rate"]
            and all(candidate[key] <= baseline[key] for key in keys)
            and (candidate["completion_rate"] > baseline["completion_rate"]
                 or any(candidate[key] < baseline[key] for key in keys)))
    return {"engines": summary, "sample_counts_sufficient": counts_sufficient,
            "metrics_only_improvement": diagnostics, "evidence_sufficient": False,
            "safety_passed": safe, "recommend_pipecat": False, "recommend_livekit": False,
            "selection_status": "BLOCKED_RAW_AGGREGATES_NOT_LIVE_EVIDENCE",
            "missing_evidence": ["paired_workloads", "recording_integrity", "source_and_environment",
                                 "independent_quality_review", "functional_candidate_certification"],
            "default_engine": "duplex"}
