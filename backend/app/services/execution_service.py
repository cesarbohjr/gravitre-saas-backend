from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.services.decision_service import DecisionPath, DecisionType, get_decision_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class NodeType(StrEnum):
    TRIGGER = "trigger"
    ACTION = "action"
    DECISION = "decision"
    LOOP = "loop"
    PARALLEL = "parallel"
    AGENT = "agent"
    HUMAN_APPROVAL = "human_approval"
    DELAY = "delay"
    END = "end"


class WorkflowNode(BaseModel):
    id: str
    type: NodeType
    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class NodeResult(BaseModel):
    node_id: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int


class RunResult(BaseModel):
    run_id: str
    status: str
    results: list[NodeResult]
    final_context: dict[str, Any]


class ExecutionService:
    def __init__(self):
        self.decision_service = get_decision_service()

    async def execute_workflow(
        self,
        org_id: str,
        workflow_id: str,
        run_id: str,
        parameters: dict | None = None,
    ) -> RunResult:
        settings = get_settings()
        client = get_supabase_client(settings)
        nodes_resp = (
            client.table("workflow_nodes")
            .select("id,node_type,name,config,order_index")
            .eq("org_id", org_id)
            .eq("workflow_id", workflow_id)
            .order("order_index", desc=False)
            .execute()
        )
        raw_nodes = nodes_resp.data or []
        nodes = [
            WorkflowNode(
                id=str(n["id"]),
                type=NodeType(str(n.get("node_type") or "action")),
                name=str(n.get("name") or "node"),
                config=n.get("config") or {},
            )
            for n in raw_nodes
        ]
        context = ExecutionContext(state=parameters or {})
        results: list[NodeResult] = []
        for node in nodes:
            result = await self.execute_node(org_id=org_id, run_id=run_id, node=node, context=context)
            results.append(result)
            context.events.append({"node_id": node.id, "status": result.status})
            if result.status == "failed":
                return RunResult(run_id=run_id, status="failed", results=results, final_context=context.state)
            if result.status == "paused":
                return RunResult(run_id=run_id, status="paused", results=results, final_context=context.state)
            context.state[node.id] = result.output
        return RunResult(run_id=run_id, status="completed", results=results, final_context=context.state)

    async def execute_node(
        self,
        org_id: str,
        run_id: str,
        node: WorkflowNode,
        context: ExecutionContext,
    ) -> NodeResult:
        start = time.perf_counter()
        try:
            if node.type == NodeType.TRIGGER:
                output = {"triggered": True}
            elif node.type == NodeType.ACTION:
                output = await self._execute_action_node(node, context)
            elif node.type == NodeType.DECISION:
                output = await self._execute_decision_node(org_id, run_id, node, context)
            elif node.type == NodeType.LOOP:
                output = await self._execute_loop_node(node, context)
            elif node.type == NodeType.PARALLEL:
                output = await self._execute_parallel_node(node, context)
            elif node.type == NodeType.HUMAN_APPROVAL:
                return NodeResult(
                    node_id=node.id,
                    status="paused",
                    output={"reason": "awaiting_human_approval"},
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )
            elif node.type == NodeType.DELAY:
                wait_s = float(node.config.get("seconds") or 1.0)
                await asyncio.sleep(min(wait_s, 10.0))
                output = {"waited_seconds": wait_s}
            else:
                output = {"completed": True}
            return NodeResult(
                node_id=node.id,
                status="completed",
                output=output,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("node execution failed: %s", str(exc))
            return NodeResult(
                node_id=node.id,
                status="failed",
                output={},
                error=str(exc),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

    async def _execute_action_node(self, node: WorkflowNode, context: ExecutionContext) -> dict[str, Any]:
        action = node.config.get("action") or "noop"
        return {"action": action, "input_keys": list(context.state.keys())}

    async def _execute_decision_node(
        self,
        org_id: str,
        run_id: str,
        node: WorkflowNode,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        paths = [
            DecisionPath(id=p.get("id"), label=p.get("label"))
            for p in (node.config.get("paths") or [{"id": "continue", "label": "Continue"}])
        ]
        result = await self.decision_service.evaluate(
            org_id=org_id,
            workflow_id=str(node.config.get("workflow_id") or ""),
            run_id=run_id,
            node_id=node.id,
            objective=str(node.config.get("objective") or node.name),
            input_data=context.state,
            available_paths=paths,
            decision_type=DecisionType.HYBRID,
            rules=node.config.get("rules") or [],
        )
        return {"selected_path": result.selected_path.id, "confidence": result.confidence}

    async def _execute_loop_node(self, node: WorkflowNode, context: ExecutionContext) -> dict[str, Any]:
        collection_key = str(node.config.get("collection_key") or "")
        items = context.state.get(collection_key, [])
        if not isinstance(items, list):
            items = []
        return {"iterations": len(items)}

    async def _execute_parallel_node(self, node: WorkflowNode, context: ExecutionContext) -> dict[str, Any]:
        branches = node.config.get("branches") or []
        await asyncio.gather(*(asyncio.sleep(0) for _ in branches))
        return {"parallel_branches": len(branches), "state_keys": len(context.state)}


_execution_service_singleton: ExecutionService | None = None


def get_execution_service() -> ExecutionService:
    global _execution_service_singleton
    if _execution_service_singleton is None:
        _execution_service_singleton = ExecutionService()
    return _execution_service_singleton
