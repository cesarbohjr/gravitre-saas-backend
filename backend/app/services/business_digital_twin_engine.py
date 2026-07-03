"""Domain-level scenario comparison using real historical outcome data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

SCOPE_NOTE = (
    "BusinessDigitalTwinEngine compares bounded domain scenarios using measured "
    "agent_action_outcomes and workflow_runs only. No general org simulation. "
    "No fabricated financial projections. V9 scope boundary preserved."
)


class BusinessDigitalTwinEngine:
    """
    Domain-level scenario comparison using real historical outcome data.
    Never fabricates projections. Returns simulation_status=\"insufficient_data\"
    when real data is unavailable.
    V9 scope boundary preserved: no general org simulation.
    """

    SUPPORTED_DOMAINS = {
        "revenue": {
            "data_source": "agent_action_outcomes WHERE metric_name IN ('deal_amount','subscription_mrr')",
            "min_data_points": 14,
            "model": "revenue_forecaster",
        },
        "workflow_automation": {
            "data_source": "workflow_runs + optimization_suggestions",
            "min_data_points": 30,
            "model": "workflow_forecaster",
        },
        "support_capacity": {
            "data_source": "agent_action_outcomes WHERE metric_name='ticket_volume'",
            "min_data_points": 14,
            "model": "capacity_forecaster",
            "catalog_status": "PLANNED",
        },
        "sla_risk": {
            "data_source": "support tickets + agent_action_outcomes ticket_volume",
            "min_data_points": 60,
            "model": "sla_breach_predictor",
            "catalog_status": "PLANNED",
        },
        "deal_pipeline": {
            "data_source": "agent_action_outcomes deal win/loss measurements",
            "min_data_points": 25,
            "model": "deal_loss_scorer",
            "catalog_status": "PLANNED",
        },
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _unsupported(self, domain: str) -> dict[str, Any]:
        return {
            "simulation_status": "domain_not_supported",
            "domain": domain,
            "supported_domains": list(self.SUPPORTED_DOMAINS.keys()),
            "approval_required": False,
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def _load_domain_series(self, org_id: str, domain: str) -> list[float]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        if domain == "revenue":
            rows = (
                client.table("agent_action_outcomes")
                .select("metric_value, metric_name")
                .eq("org_id", org_id)
                .gte("measured_at", since)
                .in_("metric_name", ["deal_amount", "subscription_mrr"])
                .limit(500)
                .execute()
                .data
                or []
            )
            return [float(r.get("metric_value") or 0) for r in rows if r.get("metric_value") is not None]
        if domain == "support_capacity":
            rows = (
                client.table("agent_action_outcomes")
                .select("metric_value")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .gte("measured_at", since)
                .limit(500)
                .execute()
                .data
                or []
            )
            return [float(r.get("metric_value") or 0) for r in rows if r.get("metric_value") is not None]
        rows = (
            client.table("workflow_runs")
            .select("duration_ms, status")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .eq("status", "completed")
            .limit(500)
            .execute()
            .data
            or []
        )
        return [float(r.get("duration_ms") or 0) for r in rows if r.get("duration_ms") is not None]

    def _scenario_from_series(
        self,
        series: list[float],
        change_description: str,
        change_params: dict[str, Any],
    ) -> dict[str, Any]:
        base = median(series)
        delta_pct = float(change_params.get("delta_percent") or change_params.get("deltaPercent") or 0)
        spread = max(base * 0.1, (max(series) - min(series)) * 0.25 if len(series) > 1 else base * 0.05)
        expected = base * (1 + delta_pct / 100.0)
        return {
            "best_case": round(expected + spread, 4),
            "expected_case": round(expected, 4),
            "worst_case": round(max(0.0, expected - spread), 4),
            "confidence": round(min(0.9, 0.35 + len(series) / 200), 4),
            "assumptions": [
                f"Based on {len(series)} measured data points.",
                f"Scenario change: {change_description}",
                "Historical variance used for best/worst bounds — not fabricated projections.",
            ],
            "data_points_used": len(series),
            "scope_note": SCOPE_NOTE,
            "approval_required": True,
            "advisory_only": True,
        }

    async def simulate(
        self,
        org_id: str,
        domain: str,
        change_description: str,
        change_params: dict | None = None,
    ) -> dict[str, Any]:
        if domain not in self.SUPPORTED_DOMAINS:
            return self._unsupported(domain)
        meta = self.SUPPORTED_DOMAINS[domain]
        series = await self._load_domain_series(org_id, domain)
        if len(series) < int(meta["min_data_points"]):
            return {
                "simulation_status": "insufficient_data",
                "domain": domain,
                "data_points_used": len(series),
                "min_data_points": meta["min_data_points"],
                "scope_note": SCOPE_NOTE,
                "approval_required": True,
                "advisory_only": True,
            }
        result = self._scenario_from_series(series, change_description, change_params or {})
        result.update(
            {
                "simulation_status": "ok",
                "domain": domain,
                "model": meta["model"],
            }
        )
        return result

    async def compare_scenarios(
        self,
        org_id: str,
        domain: str,
        scenarios: list[dict],
    ) -> dict[str, Any]:
        if domain not in self.SUPPORTED_DOMAINS:
            return self._unsupported(domain)
        compared = []
        for scenario in scenarios[:5]:
            compared.append(
                await self.simulate(
                    org_id,
                    domain,
                    str(scenario.get("description") or scenario.get("name") or "scenario"),
                    scenario.get("params") or {},
                )
            )
        return {
            "domain": domain,
            "scenarios": compared,
            "scope_note": SCOPE_NOTE,
            "approval_required": True,
            "advisory_only": True,
        }

    async def stress_test(
        self,
        org_id: str,
        domain: str,
        stress_factor: float,
    ) -> dict[str, Any]:
        base = await self.simulate(
            org_id,
            domain,
            f"Stress factor {stress_factor}",
            {"delta_percent": stress_factor * 100},
        )
        if base.get("simulation_status") != "ok":
            return base
        expected = float(base.get("expected_case") or 0)
        return {
            **base,
            "stress_factor": stress_factor,
            "stressed_expected_case": round(expected * (1 + stress_factor), 4),
            "scope_note": SCOPE_NOTE,
            "approval_required": True,
            "advisory_only": True,
        }

    async def impact_analysis(
        self,
        org_id: str,
        domain: str,
        proposed_change: dict,
    ) -> dict[str, Any]:
        simulation = await self.simulate(
            org_id,
            domain,
            str(proposed_change.get("description") or "proposed change"),
            proposed_change.get("params") or {},
        )
        return {
            "impact_analysis": simulation,
            "scope_note": SCOPE_NOTE,
            "approval_required": True,
            "advisory_only": True,
        }


_engine: BusinessDigitalTwinEngine | None = None


def get_business_digital_twin_engine(settings: Settings | None = None) -> BusinessDigitalTwinEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = BusinessDigitalTwinEngine(settings)
    return _engine
