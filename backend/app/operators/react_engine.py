"""ReAct reasoning engine for agents (STA-133 / AI-003, STA-160 / AI-026).

Reason → Act → Observe loop with LLM tool calls routed through ToolRegistry → invoke_tool.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.config import MODEL_TIERS, Settings, get_settings
from app.core.logging import get_logger
from app.operators.stream_events import ReActStreamEvent
from app.services.ai_guardrails import (
    fence_untrusted,
    harden_system_prompt,
    moderate_input,
    redact_pii,
)
from app.services.model_router import get_model_router
from app.services.providers.openai_adapter import _supports_custom_temperature
from app.services.tool_registry import ToolRegistry, get_tool_registry
from app.services.tool_types import ToolContext
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

DEFAULT_MAX_ITERATIONS = 10
_NEEDS_HUMAN_PREFIX = "NEEDS_HUMAN_INPUT:"
_OBSERVATION_MAX_CHARS = 8000


class ReActStatus(StrEnum):
    COMPLETED = "completed"
    NEEDS_HUMAN_INPUT = "needs_human_input"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    ERROR = "error"


@dataclass
class ReActTraceStep:
    iteration: int
    thought: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    observation: str | None = None
    tool_success: bool | None = None


@dataclass
class ReActResult:
    status: ReActStatus
    answer: str
    trace: list[ReActTraceStep] = field(default_factory=list)
    iterations: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "answer": self.answer,
            "iterations": self.iterations,
            "trace": [
                {
                    "iteration": step.iteration,
                    "thought": step.thought,
                    "toolName": step.tool_name,
                    "toolArgs": step.tool_args,
                    "observation": step.observation,
                    "toolSuccess": step.tool_success,
                }
                for step in self.trace
            ],
            "toolCalls": self.tool_calls,
            "error": self.error,
        }


def resolve_permitted_tools(
    agent: dict[str, Any] | None,
    explicit: list[str] | None = None,
) -> list[str]:
    """Derive permitted integration/tool names from agent row or explicit override."""
    if explicit:
        return [str(t) for t in explicit]
    if not agent:
        return ["*"]
    config = agent.get("config") or {}
    if isinstance(config, dict):
        for key in ("permitted_tools", "permittedTools", "tools"):
            raw = config.get(key)
            if isinstance(raw, list) and raw:
                return [str(t) for t in raw]
    systems = agent.get("systems") or []
    if systems:
        return [str(s) for s in systems]
    return ["*"]


def _truncate_observation(payload: Any) -> str:
    text = json.dumps(payload, default=str)
    if len(text) <= _OBSERVATION_MAX_CHARS:
        return text
    return text[: _OBSERVATION_MAX_CHARS - 20] + '..."truncated":true}'


def _parse_tool_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class ReActEngine:
    """Reason + Act + Observe loop backed by ToolRegistry and OpenAI tool calling."""

    def __init__(
        self,
        settings: Settings | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or get_tool_registry()
        self.router = get_model_router()

    async def run(
        self,
        *,
        ctx: ToolContext,
        task: str,
        system_prompt: str | None = None,
        permitted_tools: list[str] | None = None,
        connected_integrations: list[str] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        model: str | None = None,
        agent: dict[str, Any] | None = None,
        audit_resource_type: str = "agent_job",
        audit_resource_id: str | None = None,
    ) -> ReActResult:
        """Execute a ReAct loop for a single agent task."""
        from app.services.ai_tracing import trace_span

        with trace_span("react_engine.run", org_id=ctx.org_id, agent_id=ctx.agent_id):
            result: ReActResult | None = None
            async for event in self._react_loop(
                ctx=ctx,
                task=task,
                system_prompt=system_prompt,
                permitted_tools=permitted_tools,
                connected_integrations=connected_integrations,
                max_iterations=max_iterations,
                model=model,
                agent=agent,
                audit_resource_type=audit_resource_type,
                audit_resource_id=audit_resource_id,
                emit_text_deltas=False,
            ):
                if event.kind == "done":
                    result = event.react_result
            if result is None:
                return ReActResult(status=ReActStatus.ERROR, answer="", error="ReAct loop produced no result")
            return result

    async def run_streaming(
        self,
        *,
        ctx: ToolContext,
        task: str,
        system_prompt: str | None = None,
        permitted_tools: list[str] | None = None,
        connected_integrations: list[str] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        model: str | None = None,
        agent: dict[str, Any] | None = None,
        audit_resource_type: str = "agent_job",
        audit_resource_id: str | None = None,
    ) -> AsyncIterator[ReActStreamEvent]:
        """Streaming variant — same reasoning loop as run(), yields progress events."""
        async for event in self._react_loop(
            ctx=ctx,
            task=task,
            system_prompt=system_prompt,
            permitted_tools=permitted_tools,
            connected_integrations=connected_integrations,
            max_iterations=max_iterations,
            model=model,
            agent=agent,
            audit_resource_type=audit_resource_type,
            audit_resource_id=audit_resource_id,
            emit_text_deltas=True,
        ):
            yield event

    async def _react_loop(
        self,
        *,
        ctx: ToolContext,
        task: str,
        system_prompt: str | None = None,
        permitted_tools: list[str] | None = None,
        connected_integrations: list[str] | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        model: str | None = None,
        agent: dict[str, Any] | None = None,
        audit_resource_type: str = "agent_job",
        audit_resource_id: str | None = None,
        emit_text_deltas: bool,
    ) -> AsyncIterator[ReActStreamEvent]:
        """Shared ReAct implementation for run() and run_streaming()."""
        import uuid

        from app.operators.assistant_sse import chunk_text_deltas

        if getattr(self.settings, "disable_ai", False):
            yield ReActStreamEvent(
                kind="done",
                react_result=ReActResult(
                    status=ReActStatus.ERROR,
                    answer="",
                    error="AI service is disabled",
                ),
            )
            return

        try:
            await moderate_input(task, self.settings, self.router._openai)
        except Exception as exc:  # noqa: BLE001
            yield ReActStreamEvent(
                kind="done",
                react_result=ReActResult(status=ReActStatus.ERROR, answer="", error=str(exc)),
            )
            return

        allowed = resolve_permitted_tools(agent, permitted_tools)
        connected = connected_integrations
        if connected is None:
            connected = self.registry.list_connected_integrations(
                ctx.client,
                ctx.org_id,
                environment_name=ctx.environment_name,
            )

        resolved_model = model or MODEL_TIERS["high"]["openai"]
        messages: list[dict[str, Any]] = []
        hardened = harden_system_prompt(system_prompt or _default_react_system_prompt())
        if hardened:
            messages.append({"role": "system", "content": hardened})
        messages.append(
            {
                "role": "user",
                "content": fence_untrusted(redact_pii(task)),
            }
        )
        audit_id = audit_resource_id or ctx.task_id or ctx.agent_id or ctx.actor_id

        tools = await self.registry.get_available_tools(ctx.org_id, allowed, connected)
        if not tools:
            result = await self._run_reasoning_only(
                ctx=ctx,
                messages=messages,
                model=resolved_model,
                audit_resource_type=audit_resource_type,
                audit_id=audit_id,
            )
            if emit_text_deltas and result.answer:
                for piece in chunk_text_deltas(result.answer):
                    yield ReActStreamEvent(kind="text_delta", content=piece)
            yield ReActStreamEvent(kind="done", react_result=result)
            return

        allowed_tool_names = {t["function"]["name"] for t in tools}
        trace: list[ReActTraceStep] = []
        tool_calls_log: list[dict[str, Any]] = []

        for iteration in range(1, max(1, max_iterations) + 1):
            try:
                response = await self._chat_with_tools(messages, tools, resolved_model)
            except Exception as exc:  # noqa: BLE001
                logger.warning("react_model_call_failed iteration=%s error=%s", iteration, exc)
                yield ReActStreamEvent(
                    kind="done",
                    react_result=ReActResult(
                        status=ReActStatus.ERROR,
                        answer="",
                        trace=trace,
                        iterations=iteration - 1,
                        tool_calls=tool_calls_log,
                        error=str(exc),
                    ),
                )
                return

            choice = response.choices[0]
            message = choice.message
            content = (message.content or "").strip()
            tool_calls = message.tool_calls or []

            if content.upper().startswith(_NEEDS_HUMAN_PREFIX.upper()):
                question = content.split(":", 1)[-1].strip() or content
                trace.append(ReActTraceStep(iteration=iteration, thought=question))
                self._audit_iteration(
                    ctx,
                    audit_resource_type,
                    audit_id,
                    iteration,
                    thought=question,
                    status=ReActStatus.NEEDS_HUMAN_INPUT.value,
                )
                result = ReActResult(
                    status=ReActStatus.NEEDS_HUMAN_INPUT,
                    answer=question,
                    trace=trace,
                    iterations=iteration,
                    tool_calls=tool_calls_log,
                )
                if emit_text_deltas:
                    for piece in chunk_text_deltas(result.answer):
                        yield ReActStreamEvent(kind="text_delta", content=piece)
                yield ReActStreamEvent(kind="done", react_result=result)
                return

            if not tool_calls:
                final_answer = content or "Task completed."
                trace.append(ReActTraceStep(iteration=iteration, thought=final_answer))
                self._audit_iteration(
                    ctx,
                    audit_resource_type,
                    audit_id,
                    iteration,
                    thought=final_answer[:500],
                    status=ReActStatus.COMPLETED.value,
                )
                result = ReActResult(
                    status=ReActStatus.COMPLETED,
                    answer=final_answer,
                    trace=trace,
                    iterations=iteration,
                    tool_calls=tool_calls_log,
                )
                if emit_text_deltas:
                    for piece in chunk_text_deltas(final_answer):
                        yield ReActStreamEvent(kind="text_delta", content=piece)
                yield ReActStreamEvent(kind="done", react_result=result)
                return

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_message)

            for tc in tool_calls:
                tool_name = tc.function.name
                tool_args = _parse_tool_arguments(tc.function.arguments)
                call_id = f"call-{uuid.uuid4().hex[:12]}"
                if emit_text_deltas:
                    yield ReActStreamEvent(
                        kind="tool_start",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_call_id=call_id,
                    )
                observation = await self._execute_tool_call(
                    ctx,
                    tool_name,
                    tool_args,
                    allowed_tool_names=allowed_tool_names,
                )
                if emit_text_deltas:
                    yield ReActStreamEvent(
                        kind="tool_complete",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_call_id=call_id,
                        result=observation,
                    )
                tool_calls_log.append(
                    {
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": observation,
                    }
                )
                trace.append(
                    ReActTraceStep(
                        iteration=iteration,
                        thought=content or None,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        observation=_truncate_observation(observation),
                        tool_success=bool(observation.get("success")),
                    )
                )
                self._audit_iteration(
                    ctx,
                    audit_resource_type,
                    audit_id,
                    iteration,
                    tool_name=tool_name,
                    tool_success=bool(observation.get("success")),
                    status="tool_call",
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _truncate_observation(observation),
                    }
                )

                if observation.get("error_code") == "permission_denied":
                    result = ReActResult(
                        status=ReActStatus.NEEDS_HUMAN_INPUT,
                        answer=(
                            f"Tool '{tool_name}' requires additional permissions. "
                            f"{observation.get('error', 'Permission denied')}"
                        ),
                        trace=trace,
                        iterations=iteration,
                        tool_calls=tool_calls_log,
                    )
                    if emit_text_deltas:
                        for piece in chunk_text_deltas(result.answer):
                            yield ReActStreamEvent(kind="text_delta", content=piece)
                    yield ReActStreamEvent(kind="done", react_result=result)
                    return

                if (
                    observation.get("pending_approval")
                    and str(observation.get("error_code") or "") == "write_approval_required"
                ):
                    # Stop immediately — chat layer materializes format_write_approval_message.
                    # Do not stream a model-authored final answer that would race the approval UX.
                    result = ReActResult(
                        status=ReActStatus.NEEDS_HUMAN_INPUT,
                        answer="",
                        trace=trace,
                        iterations=iteration,
                        tool_calls=tool_calls_log,
                    )
                    yield ReActStreamEvent(kind="done", react_result=result)
                    return

        result = ReActResult(
            status=ReActStatus.MAX_ITERATIONS_REACHED,
            answer=(
                "Maximum reasoning iterations reached. Break this task into smaller workflow "
                "steps or provide more specific inputs."
            ),
            trace=trace,
            iterations=max_iterations,
            tool_calls=tool_calls_log,
        )
        if emit_text_deltas:
            for piece in chunk_text_deltas(result.answer):
                yield ReActStreamEvent(kind="text_delta", content=piece)
        yield ReActStreamEvent(kind="done", react_result=result)

    async def _execute_tool_call(
        self,
        ctx: ToolContext,
        tool_name: str,
        args: dict[str, Any] | None = None,
        *,
        allowed_tool_names: set[str] | frozenset[str] | None = None,
    ) -> dict[str, Any]:
        """Route a model tool call through ToolRegistry → invoke_tool."""
        if allowed_tool_names is not None and tool_name not in allowed_tool_names:
            return {
                "success": False,
                "tool": tool_name,
                "error": "Tool is not permitted or not connected for this agent",
                "error_code": "tool_not_available",
            }
        from app.services.react_write_gate import block_react_write_execution

        blocked = block_react_write_execution(tool_name, args, self.registry)
        if blocked is not None:
            return blocked
        return await self.registry.execute_tool(ctx=ctx, tool_name=tool_name, args=args)

    async def _chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> Any:
        client = self.router._openai
        if client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        if _supports_custom_temperature(model):
            kwargs["temperature"] = 0.2
        return await client.chat.completions.create(**kwargs)

    async def _run_reasoning_only(
        self,
        *,
        ctx: ToolContext,
        messages: list[dict[str, Any]],
        model: str,
        audit_resource_type: str,
        audit_id: str | None,
    ) -> ReActResult:
        """Single-pass reasoning when no integration tools are connected (STA-174)."""
        trace: list[ReActTraceStep] = []
        try:
            client = self.router._openai
            if client is None:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            kwargs: dict[str, Any] = {"model": model, "messages": messages}
            if _supports_custom_temperature(model):
                kwargs["temperature"] = 0.2
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("react_reasoning_only_failed error=%s", exc)
            return ReActResult(
                status=ReActStatus.ERROR,
                answer="",
                trace=trace,
                iterations=0,
                error=str(exc),
            )

        content = (response.choices[0].message.content or "").strip()
        if content.upper().startswith(_NEEDS_HUMAN_PREFIX.upper()):
            question = content.split(":", 1)[-1].strip() or content
            trace.append(ReActTraceStep(iteration=1, thought=question))
            self._audit_iteration(
                ctx,
                audit_resource_type,
                audit_id,
                1,
                thought=question,
                status=ReActStatus.NEEDS_HUMAN_INPUT.value,
            )
            return ReActResult(
                status=ReActStatus.NEEDS_HUMAN_INPUT,
                answer=question,
                trace=trace,
                iterations=1,
            )

        final_answer = content or "Task completed."
        trace.append(ReActTraceStep(iteration=1, thought=final_answer))
        self._audit_iteration(
            ctx,
            audit_resource_type,
            audit_id,
            1,
            thought=final_answer[:500],
            status=ReActStatus.COMPLETED.value,
        )
        return ReActResult(
            status=ReActStatus.COMPLETED,
            answer=final_answer,
            trace=trace,
            iterations=1,
        )

    @staticmethod
    def _audit_iteration(
        ctx: ToolContext,
        resource_type: str,
        resource_id: str | None,
        iteration: int,
        *,
        thought: str | None = None,
        tool_name: str | None = None,
        tool_success: bool | None = None,
        status: str = "iteration",
    ) -> None:
        if not resource_id:
            return
        write_audit_event(
            ctx.client,
            org_id=ctx.org_id,
            actor_id=ctx.actor_id,
            action="agent.react.iteration",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={
                "iteration": iteration,
                "status": status,
                "agentId": ctx.agent_id,
                "taskId": ctx.task_id,
                "toolName": tool_name,
                "toolSuccess": tool_success,
                "thoughtPreview": (thought or "")[:240] if thought else None,
            },
        )


def _default_react_system_prompt() -> str:
    return (
        "You are a Gravitre autonomous agent. Use the provided tools to research and act.\n"
        "Think step by step. Call tools when you need external data or to perform an action.\n"
        "When you need clarification from a human, respond with:\n"
        "NEEDS_HUMAN_INPUT: <your question>\n"
        "When the task is complete, respond with a concise final answer and do not call more tools."
    )


_react_engine_singleton: ReActEngine | None = None


def get_react_engine() -> ReActEngine:
    global _react_engine_singleton
    if _react_engine_singleton is None:
        _react_engine_singleton = ReActEngine()
    return _react_engine_singleton
