"""Evidence-based impact estimation before business-changing actions."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MIN_SAMPLES = 5


class SimulationService:
    """
    Estimates potential impact using historical outcome data — not a general business simulator.
    Preserves v9 digital twin scope boundary.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._recent: list[dict[str, Any]] = []

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _record_simulation(self, org_id: str, action_type: str, result: dict[str, Any]) -> None:
        entry = {"org_id": org_id, "action_type": action_type, **result}
        self._recent.append(entry)
        if len(self._recent) > 200:
            self._recent = self._recent[-200:]

    async def simulate_action(
        self,
        org_id: str,
        action_type: str,
        action_params: dict[str, Any],
    ) -> dict[str, Any]:
        handler = self._get_handler(action_type)
        if not handler:
            result = {
                "simulation_status": "not_supported",
                "action_type": action_type,
                "message": f"Simulation not yet supported for {action_type}.",
                "approval_required": True,
                "assumptions": ["No historical handler configured for this action type."],
            }
            self._record_simulation(org_id, action_type, result)
            return result
        result = await handler(org_id, action_params)
        self._record_simulation(org_id, action_type, result)
        return result

    async def simulate_workflow_change(self, org_id: str, params: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(params.get("workflow_id") or "")
        try:
            suggestions = (
                self._client()
                .table("optimization_suggestions")
                .select("id, status, suggestion_type")
                .eq("org_id", org_id)
                .limit(100)
                .execute()
                .data
                or []
            )
            runs = (
                self._client()
                .table("workflow_runs")
                .select("id, status")
                .eq("org_id", org_id)
                .eq("workflow_id", workflow_id)
                .limit(100)
                .execute()
                .data
                or []
            ) if workflow_id else []
        except Exception as exc:  # noqa: BLE001
            logger.debug("simulate_workflow_change_skipped error=%s", exc)
            suggestions, runs = [], []
        if len(suggestions) + len(runs) < MIN_SAMPLES:
            return {
                "simulation_status": "insufficient_data",
                "approval_required": True,
                "reversible": True,
                "assumptions": [
                    "Fewer than minimum historical workflow optimization samples.",
                    f"min_samples={MIN_SAMPLES}",
                ],
            }
        failure_rate = 0.0
        if runs:
            failures = sum(1 for r in runs if str(r.get("status") or "") in {"failed", "error"})
            failure_rate = failures / len(runs)
        return {
            "simulation_status": "ready",
            "approval_required": True,
            "reversible": True,
            "historical_runs": len(runs),
            "optimization_suggestions": len(suggestions),
            "estimated_failure_rate": round(failure_rate, 4),
            "assumptions": ["Based on org workflow_runs and optimization_suggestions history."],
        }

    async def simulate_campaign_change(self, org_id: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = (
                self._client()
                .table("agent_action_outcomes")
                .select("id, metric_value_before, metric_value_after")
                .eq("org_id", org_id)
                .not_.is_("measured_at", "null")
                .limit(200)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []
        if len(rows) < MIN_SAMPLES:
            return {
                "simulation_status": "insufficient_data",
                "approval_required": True,
                "reversible": False,
                "assumptions": ["Insufficient measured campaign/outcome history in agent_action_outcomes."],
            }
        deltas = []
        for row in rows:
            before, after = row.get("metric_value_before"), row.get("metric_value_after")
            if before is not None and after is not None:
                deltas.append(float(after) - float(before))
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        return {
            "simulation_status": "ready",
            "approval_required": True,
            "reversible": False,
            "sample_size": len(rows),
            "avg_metric_delta": round(avg_delta, 4),
            "assumptions": ["Correlational only — based on v8 agent_action_outcomes."],
        }

    async def simulate_bulk_update(self, org_id: str, params: dict[str, Any]) -> dict[str, Any]:
        _ = org_id
        return {
            "simulation_status": "ready",
            "approval_required": True,
            "reversible": False,
            "estimated_records_affected": params.get("record_count", "unknown"),
            "assumptions": ["Bulk CRM updates treated as irreversible unless connector confirms undo."],
            "recommended_guardrails": [
                "Preview first 10 records before bulk apply",
                "Export current state before executing",
                "Set a rollback window with connector team",
            ],
        }

    async def simulate_connector_write(self, org_id: str, params: dict[str, Any]) -> dict[str, Any]:
        connector_id = str(params.get("connector_id") or "")
        action = str(params.get("action_name") or params.get("action_type") or "write")
        return {
            "simulation_status": "ready",
            "approval_required": True,
            "reversible": bool(params.get("reversible", False)),
            "connector_id": connector_id,
            "action_name": action,
            "assumptions": [
                "All connector write actions require approval.",
                "Validated against connector write scope at execution time.",
            ],
        }

    async def compare_action_scenarios(
        self,
        org_id: str,
        scenarios: list[dict[str, Any]],
    ) -> dict[str, Any]:
        results = await asyncio.gather(
            *[
                self.simulate_action(org_id, s["action_type"], s.get("params") or {})
                for s in scenarios
            ],
            return_exceptions=True,
        )
        paired = []
        for scenario, result in zip(scenarios, results):
            if isinstance(result, Exception):
                continue
            paired.append({**scenario, "simulation": result})
        return {"scenarios": paired, "recommended": self._rank_scenarios(paired)}

    def _rank_scenarios(self, scenarios: list[dict[str, Any]]) -> dict[str, Any] | None:
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in scenarios:
            sim = item.get("simulation") or {}
            if sim.get("simulation_status") != "ready":
                continue
            benefit = float(sim.get("avg_metric_delta") or sim.get("estimated_failure_rate") or 0)
            risk = 1.0 if sim.get("reversible") is False else 0.5
            scored.append((benefit / max(risk, 0.1), item))
        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _get_handler(self, action_type: str):
        return {
            "workflow_automation_change": self.simulate_workflow_change,
            "campaign_budget_change": self.simulate_campaign_change,
            "crm_bulk_update": self.simulate_bulk_update,
            "connector_write_action": self.simulate_connector_write,
        }.get(action_type)

    async def load_admin_simulations_summary(self, org_id: str) -> dict[str, Any]:
        org_recent = [r for r in self._recent if r.get("org_id") == org_id]
        by_type: dict[str, int] = {}
        insufficient = 0
        approval_required = 0
        for row in org_recent:
            action = str(row.get("action_type") or "unknown")
            by_type[action] = by_type.get(action, 0) + 1
            if row.get("simulation_status") == "insufficient_data":
                insufficient += 1
            if row.get("approval_required"):
                approval_required += 1
        total = len(org_recent) or 1
        return {
            "simulations_run": len(org_recent),
            "approval_required_rate": round(approval_required / total, 4),
            "insufficient_data_rate": round(insufficient / total, 4),
            "by_action_type": by_type,
            "recent_simulations": org_recent[-20:],
        }


_simulation_service: SimulationService | None = None


def get_simulation_service(settings: Settings | None = None) -> SimulationService:
    global _simulation_service
    if _simulation_service is None or settings is not None:
        _simulation_service = SimulationService(settings)
    return _simulation_service
