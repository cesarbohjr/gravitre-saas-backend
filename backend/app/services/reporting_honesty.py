"""Phase 5 — reporting / insights honesty helpers.

Surfaces must not present stored, seeded, placeholder, or static metrics as if
they were live computations over current outcome / run data.
"""
from __future__ import annotations

from typing import Any, Literal

Provenance = Literal[
    "live_outcomes",
    "live_runs",
    "stored_column",
    "insufficient_data",
    "not_configured",
    "illustrative",
]

# Same spirit as Phase 4 batch degeneracy: variance expected → static is a finding.
DEFAULT_MIN_PERIODS = 3
DEFAULT_STATIC_RATIO = 0.95


def assess_metric_series(
    values: list[float | int | None],
    *,
    min_periods: int = DEFAULT_MIN_PERIODS,
    static_ratio: float = DEFAULT_STATIC_RATIO,
    metric_name: str = "metric",
) -> dict[str, Any]:
    """Flag suspiciously static series that should vary across real periods."""
    cleaned: list[float] = []
    for raw in values:
        if raw is None:
            continue
        try:
            cleaned.append(float(raw))
        except (TypeError, ValueError):
            continue

    if len(cleaned) < min_periods:
        return {
            "flagged": False,
            "reason": "series_too_short",
            "metric_name": metric_name,
            "period_count": len(cleaned),
            "min_periods": min_periods,
        }

    # Modal value dominance (exact float match after round-2)
    rounded = [round(v, 2) for v in cleaned]
    counts: dict[float, int] = {}
    for v in rounded:
        counts[v] = counts.get(v, 0) + 1
    modal_value, modal_count = max(counts.items(), key=lambda item: item[1])
    ratio = modal_count / len(rounded)
    if ratio >= static_ratio:
        return {
            "flagged": True,
            "reason": "static_value_dominance",
            "metric_name": metric_name,
            "period_count": len(rounded),
            "identical_ratio": round(ratio, 4),
            "threshold_static": static_ratio,
            "modal_value": modal_value,
            "failure_class": "degenerate_report_metric",
        }

    # Near-zero variance across periods (all within epsilon of mean)
    mean = sum(cleaned) / len(cleaned)
    if mean == 0 and all(abs(v) < 1e-9 for v in cleaned):
        return {
            "flagged": True,
            "reason": "all_zero_series",
            "metric_name": metric_name,
            "period_count": len(cleaned),
            "failure_class": "degenerate_report_metric",
        }
    spread = max(cleaned) - min(cleaned)
    relative = spread / abs(mean) if abs(mean) > 1e-9 else spread
    if relative < 0.01 and ratio >= 0.8:
        return {
            "flagged": True,
            "reason": "near_zero_variance",
            "metric_name": metric_name,
            "period_count": len(cleaned),
            "relative_spread": round(relative, 6),
            "failure_class": "degenerate_report_metric",
        }

    return {
        "flagged": False,
        "reason": "ok_variance",
        "metric_name": metric_name,
        "period_count": len(cleaned),
        "identical_ratio": round(ratio, 4),
        "modal_value": modal_value,
    }


def normalize_agent_success_rate(
    *,
    stored_rate: float | int | None,
    total_runs: int | None,
    live_outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest success-rate projection for agent list/detail surfaces.

    Never invent 100% when there is no evidence. Prefer live outcome scores when
    the outcome learning service has enough events.
    """
    runs = int(total_runs or 0)
    live = live_outcome if isinstance(live_outcome, dict) else None
    if live and live.get("status") == "ok" and live.get("score") is not None:
        score = float(live["score"])
        return {
            "success_rate": round(score * 100, 2),
            "provenance": "live_outcomes",
            "events_count": int(live.get("events_count") or 0),
            "total_runs": runs,
            "honesty_ok": True,
        }

    if runs <= 0:
        return {
            "success_rate": None,
            "provenance": "insufficient_data",
            "events_count": int((live or {}).get("events_found") or 0),
            "total_runs": runs,
            "honesty_ok": True,
            "note": "No completed runs or outcome events — rate withheld (not defaulted to 100%).",
        }

    if stored_rate is None:
        return {
            "success_rate": None,
            "provenance": "insufficient_data",
            "total_runs": runs,
            "honesty_ok": True,
        }

    try:
        rate = float(stored_rate)
    except (TypeError, ValueError):
        rate = None
    if rate is None or not (0.0 <= rate <= 100.0):
        return {
            "success_rate": None,
            "provenance": "insufficient_data",
            "total_runs": runs,
            "honesty_ok": True,
        }

    return {
        "success_rate": round(rate, 2),
        "provenance": "stored_column",
        "total_runs": runs,
        "honesty_ok": True,
        "note": "Stored operators.success_rate / agents.stats — not recomputed from outcomes this request.",
    }


def label_placeholder_metric(label: str) -> dict[str, Any]:
    """ROI / KPI slots that are not yet wired to a real computation."""
    return {
        "label": label,
        "value": None,
        "provenance": "not_configured",
        "honesty_ok": True,
        "note": "Not computed from BusinessOutcome / Module A — never shown as live.",
    }


# Canonical inventory used by live audit + docs (keep in sync with delivery doc).
REPORTING_SURFACES: list[dict[str, Any]] = [
    {
        "id": "activity_outcomes",
        "route": "/activity",
        "sot": "workflow_runs → BusinessOutcome projection",
        "risk": "low",
    },
    {
        "id": "intelligence_hub",
        "route": "/intelligence",
        "sot": "intelligence_outcome_events + model runtime_status",
        "risk": "low",
    },
    {
        "id": "metrics_ops",
        "route": "/metrics",
        "sot": "workflow_runs / connectors (live)",
        "risk": "medium",
        "notes": "UI ranges must match backend 7d|30d|90d",
    },
    {
        "id": "intelligence_reports",
        "route": "/intelligence/reports",
        "sot": "GET /api/enterprise/agent-roi + intelligence_outcome_events + pack KPIs",
        "risk": "medium",
        "notes": (
            "Agent ROI: measured model_calls cost + operational job/action counts; "
            "hours/labor/ROI labeled estimate; revenue only with monetary outcome evidence"
        ),
    },
    {
        "id": "admin_intelligence",
        "route": "/intelligence/learning",
        "sot": "audit_events + outcomes + evaluations",
        "risk": "low",
    },
    {
        "id": "golden_signals",
        "route": "/intelligence/learning (GoldenSignalsPanel)",
        "sot": "audit_events unified_turn.live.*",
        "risk": "low",
    },
    {
        "id": "built_in_models",
        "route": "/intelligence/models",
        "sot": "catalog TRAINED metadata + live runtime_status artifacts",
        "risk": "medium",
        "notes": "UI must prefer runtime_status over catalog TRAINED",
    },
    {
        "id": "agents_hub",
        "route": "/agents",
        "sot": "prefer live outcomes; else stored with provenance; never default 100%",
        "risk": "high",
    },
    {
        "id": "lite_results",
        "route": "/lite/results",
        "sot": "workflow_runs live",
        "risk": "low",
    },
    {
        "id": "pack_kpis",
        "route": "/intelligence/reports (pack tabs)",
        "sot": "marketplace installs + external_signals + knowledge_pack_cache",
        "risk": "medium",
    },
    {
        "id": "enterprise_workforce",
        "route": "/settings/enterprise",
        "sot": "agent_jobs / audit live counts; sparklines illustrative",
        "risk": "low",
    },
    {
        "id": "enterprise_agent_roi",
        "route": "/settings/enterprise?tab=roi",
        "sot": "GET /api/enterprise/agent-roi (model_calls + agent_jobs + outcomes)",
        "risk": "medium",
        "notes": "Estimates labeled; revenue not_configured unless monetary outcome metadata",
    },
    {
        "id": "marketplace_analytics",
        "route": "/marketplace/analytics",
        "sot": "marketplace usage; ROI estimates labeled",
        "risk": "medium",
    },
]
