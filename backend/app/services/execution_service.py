from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.services.decision_service import DecisionPath, DecisionType, get_decision_service
from app.services.tool_service import STEP_TYPE_TO_ACTION, invoke_tool, params_for_step
from app.services.tool_types import ToolContext
from app.workflows.constants import RUN_STATUS_COMPLETED, RUN_STATUS_FAILED
from app.workflows.execute import execute_workflow_steps
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
        *,
        user_id: str | None = None,
        definition: dict[str, Any] | None = None,
        environment_name: str = "production",
    ) -> RunResult:
        settings = get_settings()
        client = get_supabase_client(settings)
        params = parameters or {}

        if definition is None:
            run_resp = (
                client.table("workflow_runs")
                .select("definition_snapshot,triggered_by,environment_name")
                .eq("id", run_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            if run_resp.data:
                row = run_resp.data[0]
                definition = row.get("definition_snapshot") or definition
                user_id = user_id or row.get("triggered_by")
                environment_name = row.get("environment_name") or environment_name

        steps = (definition or {}).get("steps")
        if isinstance(steps, list) and steps:
            actor_id = user_id or self._resolve_actor_id(client, org_id)
            final_status, step_rows, errors, _rate_limited = await asyncio.to_thread(
                execute_workflow_steps,
                settings,
                org_id,
                str(actor_id),
                run_id,
                definition,
                params,
                client,
                environment_name,
                False,
            )
            return self._run_result_from_steps(run_id, final_status, step_rows, params, errors)

        return await self._execute_workflow_graph(
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            parameters=params,
            settings=settings,
            client=client,
        )

    def _resolve_actor_id(self, client: Any, org_id: str) -> str:
        membership = (
            client.table("organization_members")
            .select("user_id")
            .eq("org_id", org_id)
            .in_("role", ["owner", "admin", "member"])
            .limit(1)
            .execute()
        )
        if membership.data:
            return str(membership.data[0]["user_id"])
        return org_id

    def _run_result_from_steps(
        self,
        run_id: str,
        final_status: str,
        step_rows: list[dict[str, Any]],
        final_context: dict[str, Any],
        errors: list[str],
    ) -> RunResult:
        results: list[NodeResult] = []
        for row in step_rows:
            status = str(row.get("status") or "completed")
            results.append(
                NodeResult(
                    node_id=str(row.get("step_id") or row.get("id") or ""),
                    status=status,
                    output=row.get("output_snapshot") or {},
                    error=row.get("error_message"),
                    duration_ms=int(row.get("duration_ms") or 0),
                )
            )
        if not results and errors:
            results.append(
                NodeResult(
                    node_id="workflow",
                    status="failed",
                    output={},
                    error=errors[0],
                    duration_ms=0,
                )
            )
        status = "completed" if final_status == RUN_STATUS_COMPLETED else "failed"
        if final_status not in {RUN_STATUS_COMPLETED, RUN_STATUS_FAILED}:
            status = final_status
        return RunResult(
            run_id=run_id,
            status=status,
            results=results,
            final_context=final_context,
        )

    async def _execute_workflow_graph(
        self,
        *,
        org_id: str,
        workflow_id: str,
        run_id: str,
        parameters: dict[str, Any],
        settings: Any,
        client: Any,
    ) -> RunResult:
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
        context = ExecutionContext(state=parameters)
        results: list[NodeResult] = []
        for node in nodes:
            result = await self.execute_node(
                org_id=org_id,
                run_id=run_id,
                node=node,
                context=context,
                settings=settings,
                client=client,
            )
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
        *,
        settings: Any | None = None,
        client: Any | None = None,
    ) -> NodeResult:
        start = time.perf_counter()
        try:
            if node.type == NodeType.TRIGGER:
                output = {"triggered": True}
            elif node.type == NodeType.ACTION:
                output = await self._execute_action_node(
                    node,
                    context,
                    org_id=org_id,
                    run_id=run_id,
                    settings=settings or get_settings(),
                    client=client or get_supabase_client(get_settings()),
                )
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

    async def _execute_action_node(
        self,
        node: WorkflowNode,
        context: ExecutionContext,
        *,
        org_id: str,
        run_id: str,
        settings: Any,
        client: Any,
    ) -> dict[str, Any]:
        step_type = node.config.get("step_type")
        raw_action = node.config.get("tool_action") or node.config.get("action") or "noop"
        tool_action = raw_action
        if step_type and step_type in STEP_TYPE_TO_ACTION:
            tool_action = STEP_TYPE_TO_ACTION[step_type]
        elif isinstance(raw_action, str) and raw_action in STEP_TYPE_TO_ACTION:
            tool_action = STEP_TYPE_TO_ACTION[raw_action]

        if tool_action in ("noop", None) or (
            isinstance(raw_action, str) and "." not in raw_action and raw_action not in STEP_TYPE_TO_ACTION.values()
        ):
            return {"action": "noop", "input_keys": list(context.state.keys())}

        step_type_key = step_type or next(
            (k for k, v in STEP_TYPE_TO_ACTION.items() if v == tool_action),
            "noop",
        )
        ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id="",
            run_id=run_id,
            agent_id=node.config.get("agent_id"),
            connector_id=node.config.get("connector_id"),
        )
        params = params_for_step(step_type_key, node.config, context.state)
        result = await asyncio.to_thread(invoke_tool, ctx, str(tool_action), params)
        return {
            "action": tool_action,
            "success": result.success,
            "data": result.data,
            "error_code": result.error_code,
            "error": result.error_message,
        }

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
