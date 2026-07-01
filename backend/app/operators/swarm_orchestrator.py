"""Unified entry point for multi-agent swarm execution."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.swarm_coordinator_service import (
    SwarmCoordinatorError,
    SwarmSubtaskSpec,
    start_swarm,
)
from app.workflows.repository import get_supabase_client


class SwarmOrchestrator:
    """
    Wraps SwarmCoordinatorService + ExecutionCore patterns.
    Does not replace them — orchestrates them.
    All write actions remain approval-gated via existing agent permissions.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def execute_swarm_task(
        self,
        org_id: str,
        task: str,
        *,
        parent_agent_id: str,
        actor_id: str,
        department: str | None = None,
        sub_agent_ids: list[str] | None = None,
        require_approval: bool = True,
        client: Any | None = None,
    ) -> dict[str, Any]:
        _ = require_approval  # enforced by scoped tools + approvals elsewhere
        db = client or get_supabase_client(self.settings)
        agents = sub_agent_ids or []
        if not agents:
            raise SwarmCoordinatorError("At least one sub-agent is required", code="VALIDATION_ERROR")
        subtasks = [
            SwarmSubtaskSpec(
                agent_id=agent_id,
                task=task if department is None else f"[{department}] {task}",
            )
            for agent_id in agents[:5]
        ]
        return await start_swarm(
            db,
            org_id=org_id,
            parent_agent_id=parent_agent_id,
            objective=task,
            subtasks=subtasks,
            actor_id=actor_id,
            settings=self.settings,
        )


_swarm_orchestrator: SwarmOrchestrator | None = None


def get_swarm_orchestrator(settings: Settings | None = None) -> SwarmOrchestrator:
    global _swarm_orchestrator
    if _swarm_orchestrator is None or settings is not None:
        _swarm_orchestrator = SwarmOrchestrator(settings)
    return _swarm_orchestrator
