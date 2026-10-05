"""Provider-neutral scoring for the conversation parity harness."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable


DIMENSIONS = (
    "continuity",
    "correction",
    "constraint_retention",
    "clarification",
    "naturalness",
    "honesty",
    "tool_behavior",
    "governance",
    "recovery",
)


@dataclass(frozen=True)
class TrialScore:
    scenario_id: str
    provider: str
    dimensions: dict[str, float]
    passed_invariants: int
    total_invariants: int
    evidence: str = ""

    @property
    def invariant_rate(self) -> float:
        return self.passed_invariants / self.total_invariants if self.total_invariants else 0.0

    @property
    def mean_dimension_score(self) -> float:
        values = [float(v) for k, v in self.dimensions.items() if k in DIMENSIONS]
        return mean(values) if values else 0.0


def aggregate(scores: Iterable[TrialScore]) -> dict[str, object]:
    rows = list(scores)
    by_provider: dict[str, list[TrialScore]] = {}
    for row in rows:
        by_provider.setdefault(row.provider, []).append(row)
    providers: dict[str, object] = {}
    for provider, items in by_provider.items():
        providers[provider] = {
            "trials": len(items),
            "invariant_rate": round(mean(i.invariant_rate for i in items), 4),
            "mean_dimension_score": round(mean(i.mean_dimension_score for i in items), 3),
        }
    return {"providers": providers, "trial_count": len(rows)}


def parity_gate(
    gravitre: dict[str, float],
    competitor: dict[str, float],
    *,
    invariant_floor: float = 0.90,
    max_quality_gap: float = 0.5,
) -> bool:
    """Gate uses same-run competitor evidence; it does not assume vendor latency/quality."""
    return (
        float(gravitre.get("invariant_rate", 0.0)) >= invariant_floor
        and float(gravitre.get("mean_dimension_score", 0.0))
        >= float(competitor.get("mean_dimension_score", 0.0)) - max_quality_gap
    )
