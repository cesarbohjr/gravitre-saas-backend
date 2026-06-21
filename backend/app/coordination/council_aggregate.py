"""Shared-context-aware council aggregation (STA-270)."""
from __future__ import annotations

from typing import Any

from app.services.council_service import AgentCouncilService, CouncilSession, DecisionMethod


class CouncilAggregate:
    """Enrich council evidence with live sequential context before aggregation."""

    def build_swarm_evidence(
        self,
        subtasks: list[dict[str, Any]],
        *,
        shared_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "subtasks": [
                {
                    "agentId": str(row["agent_id"]),
                    "task": row["task_prompt"],
                    "result": row.get("result"),
                    "status": row["status"],
                }
                for row in subtasks
            ]
        }
        if shared_context:
            evidence["shared_context"] = shared_context
            evidence["coordination_layer"] = True
        return evidence

    def build_workflow_evidence(
        self,
        *,
        parameters: dict[str, Any],
        step_outputs: dict[str, Any],
        source_output: dict[str, Any] | None,
        shared_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "parameters": parameters,
            "prior_steps": step_outputs,
            "source_step": source_output,
        }
        if shared_context:
            evidence["shared_context"] = shared_context
            evidence["coordination_layer"] = True
        return evidence

    async def start_council(
        self,
        council: AgentCouncilService,
        *,
        org_id: str,
        workflow_id: str,
        run_id: str,
        objective: str,
        options: list[str],
        agents: list[dict[str, Any]],
        evidence: dict[str, Any],
        decision_method: DecisionMethod,
        max_rounds: int,
    ) -> CouncilSession:
        return await council.start_council(
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            objective=objective,
            options=options,
            agents=agents,
            evidence=evidence,
            decision_method=decision_method,
            max_rounds=max_rounds,
        )
