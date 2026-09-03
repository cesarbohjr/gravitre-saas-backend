"""ReAct reasoning engine for agents (STA-133 / AI-003, STA-160 / AI-026).

Reason → Act → Observe loop with LLM tool calls routed through ToolRegistry → invoke_tool.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# Phase 2 A/B — when set, consecutive reads run serially (baseline latency).
_FORCE_SERIAL_TOOLS: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "react_force_serial_tools", default=False
)


def force_serial_react_tools(enabled: bool) -> contextvars.Token[bool]:
    return _FORCE_SERIAL_TOOLS.set(bool(enabled))


def reset_serial_react_tools(token: contextvars.Token[bool]) -> None:
    _FORCE_SERIAL_TOOLS.reset(token)


def _serial_tools_forced() -> bool:
    if _FORCE_SERIAL_TOOLS.get():
        return True
    for env_name in ("GRAVITRE_REACT_SERIAL_TOOLS", "GRAVITREE_REACT_SERIAL_TOOLS"):
        if os.environ.get(env_name, "").strip().lower() in {"1", "true", "yes"}:
            return True
    return False

from app.config import MODEL_TIERS, Settings, get_settings
from app.core.logging import get_logger
from app.operators.stream_events import ReActStreamEvent
from app.services.ai_guardrails import (
    fence_untrusted,
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


def _truncate_observation(payload: Any, *, tool_name: str | None = None) -> str:
    """Truncate + Agent Security Gateway fence — tool results are DATA, never instructions."""
    from app.services.agent_security_gateway import fence_tool_observation

    return fence_tool_observation(payload, tool_name=tool_name, max_chars=_OBSERVATION_MAX_CHARS)


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
        routing_control: Any | None = None,
        tool_query: str | None = None,
        tool_classification: dict[str, Any] | None = None,
        connector_focus: tuple[str, ...] | list[str] | None = None,
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
            routing_control=routing_control,
            tool_query=tool_query,
            tool_classification=tool_classification,
            connector_focus=connector_focus,
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
        routing_control: Any | None = None,
        tool_query: str | None = None,
        tool_classification: dict[str, Any] | None = None,
        connector_focus: tuple[str, ...] | list[str] | None = None,
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

        from app.services.assistant_routing_tier import resolve_tool_loop_model

        explicit_tool_model = str(model or "").strip() or None
        resolved_model = resolve_tool_loop_model(
            explicit_model=explicit_tool_model,
            routing_control=routing_control,
            phase="planning",
            routing_tier=getattr(routing_control, "tier", "multi_step")
            if routing_control is not None
            else "multi_step",
        ) or MODEL_TIERS["high"]["openai"]
        messages: list[dict[str, Any]] = []
        from app.services.agent_security_gateway import harden_authority_system_prompt
        from app.services.gravitre_voice import apply_voice

        hardened = harden_authority_system_prompt(
            apply_voice(system_prompt or _default_react_system_prompt())
        )
        if hardened:
            messages.append({"role": "system", "content": hardened})
        messages.append(
            {
                "role": "user",
                "content": fence_untrusted(redact_pii(task)),
            }
        )
        audit_id = audit_resource_id or ctx.task_id or ctx.agent_id or ctx.actor_id

        all_tools = await self.registry.get_available_tools(ctx.org_id, allowed, connected)
        from app.services.agent_platform_optimizer import narrow_tools_for_turn

        tools, tool_visibility = narrow_tools_for_turn(
            all_tools,
            query=tool_query or task,
            classification=tool_classification,
            connector_names=tuple(connector_focus or ()),
            connected_integrations=list(connected or []),
        )
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

        # Cap must track mid-turn routing escalate (Bugbot High / routing wave).
        # Refresh before the loop condition so an escalate during iteration N
        # can still unlock rounds N+1..new_max.
        iteration = 0
        effective_max = max(1, int(max_iterations))
        if routing_control is not None:
            effective_max = max(
                effective_max,
                max(1, int(getattr(routing_control, "max_iterations", 0) or 0)),
            )

        while True:
            if routing_control is not None:
                effective_max = max(
                    effective_max,
                    max(1, int(getattr(routing_control, "max_iterations", 0) or 0)),
                )
            if iteration >= effective_max:
                break
            iteration += 1
            routing_tier = getattr(routing_control, "tier", "multi_step") if routing_control else "multi_step"
            from app.services.assistant_routing_tier import resolve_tool_loop_model

            phase = "synthesis" if iteration == effective_max else "planning"
            resolved_model = resolve_tool_loop_model(
                explicit_model=explicit_tool_model,
                routing_control=routing_control,
                phase=phase,
                routing_tier=routing_tier,
            )
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

            from app.services.providers.provider_tool_router import resolve_provider_for_model

            inference_provider = resolve_provider_for_model(resolved_model)
            if audit_id:
                from app.workflows.audit import write_audit_event

                write_audit_event(
                    ctx.client,
                    org_id=ctx.org_id,
                    actor_id=ctx.actor_id,
                    action="inference.tool_completion",
                    resource_type=audit_resource_type,
                    resource_id=audit_id,
                    metadata={
                        "provider": inference_provider,
                        "model": resolved_model,
                        "iteration": iteration,
                        "toolCallCount": len(tool_calls or []),
                        "agentId": ctx.agent_id,
                        "taskId": ctx.task_id,
                    },
                )

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

            # Phase 2 — parallelize consecutive independent *read* tools in one
            # model turn. Writes stay serial + gated (approval short-circuit).
            from app.services.react_write_gate import tool_requires_user_write_approval
            from app.services.tool_error_messages import (
                REACT_SHORT_CIRCUIT_ERROR_CODES,
                format_tool_error_for_user,
                integration_from_tool_name,
            )

            prepared: list[tuple[Any, str, dict[str, Any], str, bool]] = []
            for tc in tool_calls:
                tool_name = tc.function.name
                tool_args = _parse_tool_arguments(tc.function.arguments)
                call_id = f"call-{uuid.uuid4().hex[:12]}"
                requires_write, *_ = tool_requires_user_write_approval(tool_name, self.registry)
                prepared.append((tc, tool_name, tool_args, call_id, bool(requires_write)))

            idx = 0
            short_circuit_result: ReActResult | None = None
            while idx < len(prepared) and short_circuit_result is None:
                _, _, _, _, is_write = prepared[idx]
                if is_write:
                    batch = [prepared[idx]]
                    idx += 1
                    parallel = False
                else:
                    batch = []
                    while idx < len(prepared) and not prepared[idx][4]:
                        batch.append(prepared[idx])
                        idx += 1
                    # A/B baseline: force serial even when multiple reads are present.
                    parallel = len(batch) > 1 and not _serial_tools_forced()

                for tc, tool_name, tool_args, call_id, requires_write in batch:
                    if routing_control is not None:
                        from app.services.assistant_routing_tier import escalate_for_write_tool

                        if escalate_for_write_tool(
                            routing_control, tool_is_write=bool(requires_write)
                        ):
                            esc = routing_control.escalations[-1]
                            yield ReActStreamEvent(kind="routing_escalation", result=esc)
                    if emit_text_deltas:
                        yield ReActStreamEvent(
                            kind="tool_start",
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_call_id=call_id,
                        )

                started = time.perf_counter()
                if parallel:
                    observations = list(
                        await asyncio.gather(
                            *[
                                self._execute_tool_call(
                                    ctx,
                                    tool_name,
                                    tool_args,
                                    allowed_tool_names=allowed_tool_names,
                                )
                                for _tc, tool_name, tool_args, _cid, _w in batch
                            ]
                        )
                    )
                else:
                    # Single tool, or Phase-2 A/B serial baseline for multi-read batches.
                    observations = []
                    for _tc, tool_name, tool_args, _cid, _w in batch:
                        observations.append(
                            await self._execute_tool_call(
                                ctx,
                                tool_name,
                                tool_args,
                                allowed_tool_names=allowed_tool_names,
                            )
                        )
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                batch_id = f"i{iteration}-b{idx}-{len(batch)}"

                for (tc, tool_name, tool_args, call_id, _w), observation in zip(
                    batch, observations, strict=True
                ):
                    if emit_text_deltas:
                        yield ReActStreamEvent(
                            kind="tool_complete",
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_call_id=call_id,
                            result=observation,
                        )
                    if routing_control is not None and isinstance(observation, dict):
                        from app.services.assistant_routing_tier import record_tool_outcome

                        if record_tool_outcome(
                            routing_control,
                            success=bool(observation.get("success")),
                            error_code=str(observation.get("error_code") or "") or None,
                        ):
                            esc = routing_control.escalations[-1]
                            yield ReActStreamEvent(kind="routing_escalation", result=esc)
                    tool_calls_log.append(
                        {
                            "iteration": iteration,
                            "tool": tool_name,
                            "args": tool_args,
                            "result": observation,
                            "parallel_batch": parallel,
                            "batch_id": batch_id,
                            # Wall time for the whole batch (shared across members).
                            "batch_elapsed_ms": elapsed_ms,
                        }
                    )
                    trace.append(
                        ReActTraceStep(
                            iteration=iteration,
                            thought=content or None,
                            tool_name=tool_name,
                            tool_args=tool_args,
                            observation=_truncate_observation(observation, tool_name=tool_name),
                            tool_success=bool(observation.get("success")),
                        )
                    )
                    self._audit_iteration(
                        ctx,
                        audit_resource_type,
                        audit_id,
                        iteration,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        observation=observation if isinstance(observation, dict) else None,
                        tool_success=bool(observation.get("success")),
                        status="tool_call",
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": _truncate_observation(observation, tool_name=tool_name),
                        }
                    )

                    if (
                        observation.get("pending_approval")
                        and str(observation.get("error_code") or "")
                        == "write_approval_required"
                    ):
                        short_circuit_result = ReActResult(
                            status=ReActStatus.NEEDS_HUMAN_INPUT,
                            answer="",
                            trace=trace,
                            iterations=iteration,
                            tool_calls=tool_calls_log,
                        )
                        break

                    error_code = str(observation.get("error_code") or "").strip().lower()
                    if (
                        observation.get("success") is False
                        and error_code in REACT_SHORT_CIRCUIT_ERROR_CODES
                    ):
                        answer = format_tool_error_for_user(
                            error_code,
                            str(observation.get("error") or ""),
                            integration=integration_from_tool_name(tool_name),
                            action=str(observation.get("action") or ""),
                        )
                        short_circuit_result = ReActResult(
                            status=ReActStatus.NEEDS_HUMAN_INPUT,
                            answer=answer,
                            trace=trace,
                            iterations=iteration,
                            tool_calls=tool_calls_log,
                        )
                        break

            if short_circuit_result is not None:
                if short_circuit_result.answer and emit_text_deltas:
                    for piece in chunk_text_deltas(short_circuit_result.answer):
                        yield ReActStreamEvent(kind="text_delta", content=piece)
                yield ReActStreamEvent(kind="done", react_result=short_circuit_result)
                return

        result = ReActResult(
            status=ReActStatus.MAX_ITERATIONS_REACHED,
            answer=(
                "Maximum reasoning iterations reached. Break this task into smaller workflow "
                "steps or provide more specific inputs."
            ),
            trace=trace,
            iterations=iteration,
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
        from app.services.react_write_gate import (
            block_react_write_execution,
            tool_requires_user_write_approval,
        )

        connected: list[str] = []
        if ctx.client and ctx.org_id:
            connected = self.registry.list_connected_integrations(
                ctx.client,
                ctx.org_id,
                environment_name=ctx.environment_name,
            )

        requires_write, invoke_action, *_rest = tool_requires_user_write_approval(
            tool_name,
            self.registry,
            connected_integrations=connected,
        )
        # Canvas agent steps: when ToolContext.run_id is a workflow_runs row,
        # honor run-level catalog write authority (same SoT) instead of the
        # chat turn-level pending gate — closes the agent/council canvas gap.
        if requires_write and ctx.run_id and ctx.client:
            from app.services.canvas_write_gate import (
                CANVAS_WRITE_AUTHORITY_BLOCKED,
                load_run_for_write_gate,
                run_allows_catalog_write_execution,
            )
            from app.services.gravitre_voice import format_operator_message

            run_row = load_run_for_write_gate(ctx.client, ctx.org_id, ctx.run_id)
            if run_row is not None:
                if run_allows_catalog_write_execution(run_row):
                    return await self.registry.execute_tool(
                        ctx=ctx, tool_name=tool_name, args=args
                    )
                return {
                    "success": False,
                    "tool": tool_name,
                    "action": invoke_action,
                    "error_code": CANVAS_WRITE_AUTHORITY_BLOCKED,
                    "error": format_operator_message(
                        "canvas_write_blocked",
                        confidence_register="blocked",
                        allow_humor=False,
                    ),
                }

        blocked = block_react_write_execution(
            tool_name,
            args,
            self.registry,
            client=ctx.client,
            org_id=ctx.org_id,
            user_id=ctx.actor_id,
            agent_id=ctx.agent_id,
            settings=self.settings,
        )
        if blocked is not None:
            return blocked
        return await self.registry.execute_tool(ctx=ctx, tool_name=tool_name, args=args)

    async def _chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> Any:
        from app.services.providers.provider_tool_router import complete_with_tools

        temp = 0.2 if _supports_custom_temperature(model) else None
        return await complete_with_tools(
            self.router,
            model=model,
            messages=messages,
            tools=tools if tools else [],
            tool_choice="auto",
            temperature=temp,
        )

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
        tool_args: dict[str, Any] | None = None,
        observation: dict[str, Any] | None = None,
        tool_success: bool | None = None,
        status: str = "iteration",
    ) -> None:
        if not resource_id:
            return
        obs = observation if isinstance(observation, dict) else None
        error = None
        error_code = None
        if obs is not None:
            raw_error = obs.get("error")
            if raw_error is not None:
                error = str(raw_error)[:500]
            raw_code = obs.get("error_code")
            if raw_code is not None:
                error_code = str(raw_code)[:120]
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
                "toolArgs": tool_args,
                "observation": _truncate_observation(obs, tool_name=tool_name)
                if obs is not None
                else None,
                "error": error,
                "errorCode": error_code,
                "toolSuccess": tool_success,
                "thoughtPreview": (thought or "")[:240] if thought else None,
            },
        )


def _default_react_system_prompt() -> str:
    # Voice is applied at the call site via apply_voice (idempotent).
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
