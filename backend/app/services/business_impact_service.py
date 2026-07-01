"""Aggregate v8 outcomes + v10 suggestions into Revenue Risk and Business Impact views."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.optimization_suggestion_service import (
    POOR_OUTCOME_WIN_RATE,
    _serialize_suggestion,
)
from app.services.outcome_attribution_service import get_outcome_attribution_service
from app.workflows.repository import get_supabase_client

BUSINESS_SIGNAL_SUGGESTION_TYPES = frozenset(
    {
        "stalled_deal",
        "overdue_invoice",
        "support_backlog_growth",
        "post_publish_marketing_underperformance",
        "poor_outcome_pattern",
    }
)

RISK_SEVERITY_BY_TYPE = {
    "overdue_invoice": "high",
    "stalled_deal": "high",
    "support_backlog_growth": "medium",
    "post_publish_marketing_underperformance": "medium",
    "poor_outcome_pattern": "medium",
    "slow_step": "low",
    "duplicate_step": "low",
    "low_reliability_reference": "low",
}

RISK_PENALTY_BY_SEVERITY = {"high": 12, "medium": 7, "low": 3}


def _risk_title(suggestion_type: str) -> str:
    labels = {
        "stalled_deal": "Stalled deals",
        "overdue_invoice": "Overdue invoices",
        "support_backlog_growth": "Support backlog growth",
        "post_publish_marketing_underperformance": "Marketing underperformance",
        "poor_outcome_pattern": "Poor outcome pattern",
        "slow_step": "Slow workflow step",
        "duplicate_step": "Duplicate workflow step",
        "low_reliability_reference": "Low-reliability source",
    }
    return labels.get(suggestion_type, suggestion_type.replace("_", " ").title())


async def load_business_impact_snapshot(
    org_id: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    client = get_supabase_client(active_settings)

    pending = (
        client.table("optimization_suggestions")
        .select("*")
        .eq("org_id", org_id)
        .eq("status", "pending_review")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )

    revenue_risk_items: list[dict[str, Any]] = []
    penalty = 0
    business_signal_count = 0

    for row in pending:
        suggestion_type = str(row.get("suggestion_type") or "")
        serialized = _serialize_suggestion(row)
        severity = RISK_SEVERITY_BY_TYPE.get(suggestion_type, "low")
        penalty += RISK_PENALTY_BY_SEVERITY.get(severity, 3)
        if suggestion_type in BUSINESS_SIGNAL_SUGGESTION_TYPES:
            business_signal_count += 1
        revenue_risk_items.append(
            {
                "id": str(row.get("id") or ""),
                "severity": severity,
                "title": _risk_title(suggestion_type),
                "summary": str(row.get("suggested_action") or ""),
                "explanation": serialized.get("explanation"),
                "source": "optimization_suggestion",
                "suggestionType": suggestion_type,
                "status": row.get("status"),
                "createdAt": row.get("created_at"),
            }
        )

    outcome_service = get_outcome_attribution_service(active_settings)
    agents = (
        client.table("agents")
        .select("id, name")
        .eq("org_id", org_id)
        .limit(200)
        .execute()
        .data
        or []
    )
    poor_outcome_agents = 0
    outcome_health_scores: list[float] = []
    for agent in agents:
        agent_id = str(agent.get("id") or "")
        if not agent_id:
            continue
        summary = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
        if not summary.get("sufficientData"):
            continue
        win_rate = float(summary.get("winRate") or 0.0)
        outcome_health_scores.append(win_rate)
        if win_rate < POOR_OUTCOME_WIN_RATE:
            poor_outcome_agents += 1
            penalty += 8
            revenue_risk_items.append(
                {
                    "id": f"outcome-{agent_id}",
                    "severity": "medium",
                    "title": f"Low win rate: {agent.get('name') or agent_id}",
                    "summary": (
                        f"Observed win rate is {int(win_rate * 100)}% across "
                        f"{summary.get('sampleSize')} measured actions."
                    ),
                    "explanation": str(summary.get("confidenceNote") or ""),
                    "source": "outcome_attribution",
                    "suggestionType": "poor_outcome_pattern",
                    "status": "observed",
                    "createdAt": None,
                }
            )

    avg_outcome_health = (
        round(sum(outcome_health_scores) / len(outcome_health_scores), 2)
        if outcome_health_scores
        else None
    )
    business_impact_score = max(0, min(100, 100 - penalty))
    if business_impact_score >= 80:
        score_label = "healthy"
    elif business_impact_score >= 60:
        score_label = "moderate"
    else:
        score_label = "at_risk"

    return {
        "scopeNote": (
            "Business Impact Score aggregates pending v10 optimization suggestions and v8 outcome "
            "summaries. Correlational only — review evidence before acting."
        ),
        "businessImpactScore": business_impact_score,
        "scoreLabel": score_label,
        "pendingReviewCount": len(pending),
        "pendingBusinessSignals": business_signal_count,
        "poorOutcomeAgents": poor_outcome_agents,
        "avgOutcomeWinRate": avg_outcome_health,
        "revenueRiskItems": revenue_risk_items[:25],
        "dimensions": {
            "revenueRisk": max(0, 100 - min(100, business_signal_count * 15)),
            "outcomeHealth": int((avg_outcome_health or 0.5) * 100),
            "operationalLoad": max(0, 100 - min(100, len(pending) * 4)),
        },
    }
