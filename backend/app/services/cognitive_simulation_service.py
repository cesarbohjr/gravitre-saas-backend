"""Honest business what-if simulation (Module C) for CognitiveTurnKernel Phase 6."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_DISCLAIMER = (
    "This is a heuristic scenario projection, not a factual forecast. "
    "It is not based on a trained predictive model of your business. "
    "Do not treat qualitative directions as measured outcomes or product SKUs."
)


async def simulate_business_scenario(
    *,
    org_id: str,
    scenario: str,
    assumptions: list[str] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Produce an honest qualitative what-if projection.

    Never invents dollar prices as product SKUs. Always stamps Module C honesty fields.
    """
    if not org_id:
        return {
            "ok": False,
            "error": "org_id is required",
            "assumptions": [],
            "confidenceSource": "heuristic",
            "confidenceIsEstimate": True,
            "disclaimer": _DISCLAIMER,
            "isFact": False,
            "moduleCHonesty": {
                "confidenceSource": "heuristic",
                "confidenceIsEstimate": True,
                "isFact": False,
                "disclaimer": _DISCLAIMER,
            },
        }

    assumption_list = _normalize_assumptions(assumptions, scenario)
    scenario_text = (scenario or "").strip()
    direction = _heuristic_direction(scenario_text)

    projections = [
        {
            "dimension": "relative_volume",
            "direction": direction.get("volume", "unclear"),
            "note": "Qualitative only — no absolute counts claimed.",
        },
        {
            "dimension": "relative_effort",
            "direction": direction.get("effort", "unclear"),
            "note": "Relative operational load vs current baseline (estimate).",
        },
        {
            "dimension": "relative_risk",
            "direction": direction.get("risk", "unclear"),
            "note": "Directional risk lean — not a quantified risk score.",
        },
    ]

    return {
        "ok": True,
        "org_id": org_id,
        "scenario": scenario_text,
        "assumptions": assumption_list,
        "projections": projections,
        "summary": (
            f"Heuristic what-if for org-scoped scenario: {scenario_text[:200] or '(empty)'}. "
            "Directions are relative, not dollar or SKU claims."
        ),
        "confidenceSource": "heuristic",
        "confidenceIsEstimate": True,
        "disclaimer": _DISCLAIMER,
        "isFact": False,
        "moduleCHonesty": {
            "confidenceSource": "heuristic",
            "confidenceIsEstimate": True,
            "isFact": False,
            "disclaimer": _DISCLAIMER,
            "neverInventPrices": True,
            "projectionKind": "qualitative_relative",
        },
    }


def _normalize_assumptions(
    assumptions: list[str] | dict[str, Any] | None,
    scenario: str,
) -> list[str]:
    out: list[str] = []
    if isinstance(assumptions, list):
        out.extend(str(a) for a in assumptions if a is not None and str(a).strip())
    elif isinstance(assumptions, dict):
        for key, value in assumptions.items():
            out.append(f"{key}: {value}")
    if not out:
        out = [
            "Current operating baseline remains otherwise unchanged",
            "No external market shock beyond the stated scenario",
            f"Scenario text interpreted literally: {(scenario or '')[:120] or '(none)'}",
        ]
    # Strip anything that looks like a fabricated SKU price claim in assumptions.
    cleaned: list[str] = []
    for item in out:
        text = str(item)
        if "$" in text and any(tok in text.lower() for tok in ("sku", "price", "/mo", "per month")):
            cleaned.append(
                "Assumption redacted: dollar/SKU pricing is not invented by this simulator"
            )
        else:
            cleaned.append(text)
    return cleaned


def _heuristic_direction(scenario: str) -> dict[str, str]:
    text = scenario.lower()
    volume = "unclear"
    effort = "unclear"
    risk = "unclear"
    if any(tok in text for tok in ("reduce", "cut", "-30%", "decrease", "less", "lower")):
        volume = "likely_lower"
        effort = "likely_lower_or_mixed"
        risk = "may_increase_if_capacity_lost"
    elif any(tok in text for tok in ("increase", "grow", "expand", "more", "raise", "+")):
        volume = "likely_higher"
        effort = "likely_higher"
        risk = "may_increase_with_scale"
    elif any(tok in text for tok in ("automate", "delegate", "outsource")):
        volume = "stable_to_higher"
        effort = "likely_lower_manual"
        risk = "process_and_quality_risk"
    return {"volume": volume, "effort": effort, "risk": risk}
