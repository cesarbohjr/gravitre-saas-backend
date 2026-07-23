"""Single-call turn reasoning (shadow path) — replaces classify-then-route over time.

Phase 1: shadow only — one model call with conversation, pending context, and
narrowed native tool schemas. Does not execute tools or change user-visible output.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from typing import Any, Literal

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.gravitree_voice import apply_voice, voice_system_prompt_section
from app.services.model_router import get_model_router
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
from app.services.providers.openai_adapter import _supports_custom_temperature
from app.services.react_write_gate import tool_requires_user_write_approval
from app.services.tool_registry import get_tool_registry
from app.services.unified_turn_pending_context import build_unified_turn_pending_context
from app.services.unified_turn_tool_retrieval import (
    embed_narrow_tools_for_turn,
    is_task_shaped_for_retrieval,
)
from app.services.user_facing_copy_guard import assert_no_raw_catalog_action_keys, finalize_user_facing_message

logger = get_logger(__name__)

# Keep strong refs so fire-and-forget shadow tasks are not GC'd when the chat
# request ends quickly (conversational early-exit).
_SHADOW_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()

UnifiedOutcomeKind = Literal[
    "conversational_reply",
    "clarifying_question",
    "confirmation_request",
    "connector_tool_proposal",
    "knowledge_boundary",
    "error",
    "skipped",
]


@dataclass
class UnifiedTurnShadowResult:
    outcome_kind: UnifiedOutcomeKind = "skipped"
    user_message: str = ""
    tool_name: str | None = None
    tool_invoke_action: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    requires_write_approval: bool = False
    latency_ms: int = 0
    tool_stats: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    error: str | None = None
    first_token_proxy_ms: int | None = None  # wall clock: shadow start → first stream delta
    streamed: bool = False
    live_served: bool = False  # Phase 4: outcome used for user-visible response
    # Phase timings + tool payload (see latency_breakdown keys in run_unified_turn_shadow).
    latency_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_audit_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["user_message"] = (self.user_message or "")[:1200]
        if self.tool_arguments:
            payload["tool_arguments"] = {
                k: str(v)[:200] for k, v in list(self.tool_arguments.items())[:20]
            }
        live = bool(self.live_served)
        payload["shadow_user_visible"] = live
        payload["classical_path_active"] = not live
        payload["shadow_executes_tools"] = False  # tools still go through write/execute gates
        return payload


@dataclass
class _StreamedCompletion:
    content: str
    tool_calls: list[Any]
    first_token_ms: int | None  # relative to wall_start
    model_ttft_ms: int | None  # relative to model_start (create() call)
    latency_ms: int  # wall_start → stream end
    model_total_ms: int  # model_start → stream end
    streamed: bool


async def _complete_unified_turn_stream(
    openai_client: Any,
    *,
    kwargs: dict[str, Any],
    wall_start: float,
    model_start: float,
) -> _StreamedCompletion:
    """Stream the shadow completion; record wall TTFT and model-only TTFT."""
    stream_kwargs = {**kwargs, "stream": True}
    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    first_token_ms: int | None = None
    model_ttft_ms: int | None = None

    stream = await openai_client.chat.completions.create(**stream_kwargs)
    async for chunk in stream:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            continue
        piece = getattr(delta, "content", None) or ""
        if piece:
            if first_token_ms is None:
                now = time.perf_counter()
                first_token_ms = int((now - wall_start) * 1000)
                model_ttft_ms = int((now - model_start) * 1000)
            content_parts.append(str(piece))
        for tc_delta in getattr(delta, "tool_calls", None) or []:
            if first_token_ms is None:
                now = time.perf_counter()
                first_token_ms = int((now - wall_start) * 1000)
                model_ttft_ms = int((now - model_start) * 1000)
            idx = int(getattr(tc_delta, "index", 0) or 0)
            slot = tool_acc.setdefault(
                idx,
                {"id": None, "function": {"name": "", "arguments": ""}},
            )
            if getattr(tc_delta, "id", None):
                slot["id"] = tc_delta.id
            fn = getattr(tc_delta, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    slot["function"]["name"] = str(fn.name or "")
                if getattr(fn, "arguments", None):
                    slot["function"]["arguments"] = (
                        str(slot["function"].get("arguments") or "") + str(fn.arguments or "")
                    )

    tool_calls: list[Any] = []
    for idx in sorted(tool_acc):
        slot = tool_acc[idx]
        name = str(slot["function"].get("name") or "")
        if not name:
            continue
        tool_calls.append(
            SimpleNamespace(
                id=slot.get("id"),
                type="function",
                function=SimpleNamespace(
                    name=name,
                    arguments=slot["function"].get("arguments") or "{}",
                ),
            )
        )

    end = time.perf_counter()
    latency_ms = int((end - wall_start) * 1000)
    model_total_ms = int((end - model_start) * 1000)
    if first_token_ms is None and (content_parts or tool_calls):
        first_token_ms = latency_ms
        model_ttft_ms = model_total_ms
    return _StreamedCompletion(
        content="".join(content_parts).strip(),
        tool_calls=tool_calls,
        first_token_ms=first_token_ms,
        model_ttft_ms=model_ttft_ms,
        latency_ms=latency_ms,
        model_total_ms=model_total_ms,
        streamed=True,
    )


def _history_to_messages(
    conversation_history: list[dict[str, Any]] | None,
    *,
    max_turns: int = 12,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in list(conversation_history or [])[-max_turns:]:
        role = str(row.get("role") or "").strip().lower()
        content = str(row.get("content") or row.get("message") or "").strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def _last_assistant_snippet(conversation_history: list[dict[str, Any]] | None) -> str | None:
    for row in reversed(list(conversation_history or [])):
        if str(row.get("role") or "").lower() == "assistant":
            text = str(row.get("content") or row.get("message") or "").strip()
            return text or None
    return None


def _resolve_model(settings: Settings, *, task_shaped: bool = False) -> str:
    from app.config import MODEL_TIERS

    if task_shaped:
        tier_name = str(getattr(settings, "unified_turn_task_model_tier", "") or "").strip().lower()
        if tier_name:
            tier = MODEL_TIERS.get(tier_name) or {}
            model = str(tier.get("openai") or "").strip()
            if model:
                return model
    # Historical default for unified turn (social + unset task tier).
    tier = MODEL_TIERS.get("standard") or MODEL_TIERS.get("fast") or {}
    return str(tier.get("openai") or "gpt-4o-mini")


async def run_unified_turn_shadow(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    message: str,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    connected_integrations: list[str] | None,
    client: Any = None,
    settings: Settings | None = None,
) -> UnifiedTurnShadowResult:
    """One model call; does not execute tools (Phase 4 may serve text to the user)."""
    active = settings or get_settings()
    shadow_on = bool(getattr(active, "unified_turn_shadow_enabled", False))
    live_on = bool(getattr(active, "unified_turn_live_enabled", False))
    if not shadow_on and not live_on:
        return UnifiedTurnShadowResult(outcome_kind="skipped")

    if not (active.openai_api_key or "").strip():
        return UnifiedTurnShadowResult(outcome_kind="error", error="openai_not_configured")

    wall_start = time.perf_counter()
    registry = get_tool_registry()
    permitted = ["*"]
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    all_tools = registry.get_tools_for_agent(permitted, connected)
    t_after_registry = time.perf_counter()

    use_embed, shape_label, retrieval_query = is_task_shaped_for_retrieval(message or "")
    embed_on = bool(getattr(active, "unified_turn_embedding_tool_retrieval", True)) and use_embed
    if use_embed:
        max_tools = int(
            getattr(active, "unified_turn_task_max_tools", None)
            or getattr(active, "unified_turn_shadow_max_tools", 32)
            or 16
        )
    else:
        max_tools = int(getattr(active, "unified_turn_shadow_max_tools", 32) or 32)

    if embed_on:
        visible, tool_stats = embed_narrow_tools_for_turn(
            all_tools,
            query=retrieval_query or message,
            settings=active,
            org_id=org_id,
            connected_integrations=connected,
            requires_action=None,
            max_tools=max_tools,
        )
    else:
        visible, tool_stats = narrow_tools_for_turn(
            all_tools,
            query=message,
            connected_integrations=connected,
            requires_action=None,
            max_tools=max_tools,
        )
        tool_stats = {
            **(tool_stats or {}),
            "retrievalMethod": "keyword_narrow_tools_for_turn",
            "embeddingToolRetrieval": False,
        }
    t_after_narrow = time.perf_counter()

    pending_block = build_unified_turn_pending_context(
        task_state,
        last_assistant_message=_last_assistant_snippet(conversation_history),
    )
    # Full Module D spec is the system instruction (not a post-hoc phrase bank).
    system = apply_voice(
        build_module_d_unified_system_prompt(
            extra_operator_rules=voice_system_prompt_section(),
        )
    )
    user_parts = []
    if pending_block:
        user_parts.append(pending_block)
    # Explicit tool inventory note for knowledge-boundary honesty.
    if visible:
        names = sorted(
            {
                str(t.get("function", {}).get("name") or t.get("name") or "")
                for t in visible
                if isinstance(t, dict)
            }
        )
        names = [n for n in names if n][:40]
        user_parts.append(
            "AVAILABLE TOOLS THIS TURN (schemas attached as functions; "
            "you have NO other live data sources):\n- "
            + "\n- ".join(names)
        )
    else:
        user_parts.append(
            "AVAILABLE TOOLS THIS TURN: none. Do not invent metrics, run counts, "
            "or connector results."
        )
    user_parts.append(f"USER MESSAGE:\n{(message or '').strip()}")
    user_content = "\n\n".join(user_parts)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(_history_to_messages(conversation_history))
    messages.append({"role": "user", "content": user_content})
    t_after_prompt = time.perf_counter()

    tools_payload_bytes = len(json.dumps(visible, separators=(",", ":")).encode("utf-8"))
    messages_chars = sum(len(str(m.get("content") or "")) for m in messages)
    system_prompt_chars = len(system or "")
    # Hypothetical full-catalog payload for the same connected set (not sent).
    full_catalog_bytes = len(json.dumps(all_tools, separators=(",", ":")).encode("utf-8"))

    model = _resolve_model(active, task_shaped=use_embed)
    router = get_model_router()
    openai_client = router._openai  # noqa: SLF001 — same pattern as react_engine
    if openai_client is None:
        return UnifiedTurnShadowResult(outcome_kind="error", error="openai_client_unavailable")

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "tools": visible,
        "tool_choice": "auto",
    }
    if _supports_custom_temperature(model):
        kwargs["temperature"] = 0.2

    retrieval_method = str(
        (tool_stats or {}).get("retrievalMethod")
        or ("embedding_narrow_tools_for_turn" if embed_on else "keyword_narrow_tools_for_turn")
    )
    embedding_used = bool((tool_stats or {}).get("embeddingToolRetrieval"))
    breakdown: dict[str, Any] = {
        "registry_tools_ms": int((t_after_registry - wall_start) * 1000),
        "narrow_tools_ms": int((t_after_narrow - t_after_registry) * 1000),
        "context_prompt_ms": int((t_after_prompt - t_after_narrow) * 1000),
        "pre_model_ms": int((t_after_prompt - wall_start) * 1000),
        "tools_payload_bytes": tools_payload_bytes,
        "full_catalog_payload_bytes": full_catalog_bytes,
        "system_prompt_chars": system_prompt_chars,
        "messages_chars": messages_chars,
        "total_tools": len(all_tools),
        "visible_tools": len(visible),
        "max_tools_cap": max_tools,
        "retrieval_method": retrieval_method,
        "embedding_tool_retrieval": embedding_used,
        "turn_shape_hint": shape_label,
        "retrieval_query": (retrieval_query or "")[:240],
        "task_model_tier": str(getattr(active, "unified_turn_task_model_tier", "") or "") or None,
    }
    tool_stats = {
        **(tool_stats or {}),
        "toolsPayloadBytes": tools_payload_bytes,
        "fullCatalogPayloadBytes": full_catalog_bytes,
        "turnShapeHint": shape_label,
    }

    try:
        model_start = time.perf_counter()
        breakdown["openai_create_schedule_ms"] = int((model_start - t_after_prompt) * 1000)
        completion = await _complete_unified_turn_stream(
            openai_client,
            kwargs=kwargs,
            wall_start=wall_start,
            model_start=model_start,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("unified_turn_shadow model call failed: %s", exc)
        breakdown["error"] = str(exc)[:200]
        return UnifiedTurnShadowResult(
            outcome_kind="error",
            error=str(exc)[:500],
            latency_ms=int((time.perf_counter() - wall_start) * 1000),
            tool_stats=tool_stats,
            model=model,
            latency_breakdown=breakdown,
        )

    content = completion.content
    tool_calls = completion.tool_calls
    latency_ms = completion.latency_ms
    breakdown["model_ttft_ms"] = completion.model_ttft_ms
    breakdown["model_total_ms"] = completion.model_total_ms
    breakdown["wall_to_first_token_ms"] = completion.first_token_ms
    # Residual after model_ttft inside wall TTFT ≈ pre_model + network/queue inside create().
    if completion.first_token_ms is not None and completion.model_ttft_ms is not None:
        breakdown["pre_first_token_overhead_ms"] = max(
            0, int(completion.first_token_ms) - int(completion.model_ttft_ms)
        )

    result = UnifiedTurnShadowResult(
        latency_ms=latency_ms,
        first_token_proxy_ms=completion.first_token_ms,
        streamed=completion.streamed,
        tool_stats=tool_stats,
        model=model,
        latency_breakdown=breakdown,
    )

    if tool_calls:
        tc = tool_calls[0]
        tool_name = str(tc.function.name or "")
        args = {}
        try:
            parsed = json.loads(tc.function.arguments or "{}")
            if isinstance(parsed, dict):
                args = parsed
        except json.JSONDecodeError:
            args = {}
        spec = registry._specs.get(tool_name)  # noqa: SLF001
        invoke = str(getattr(spec, "invoke_action", "") or "") if spec else ""
        requires_write, *_ = tool_requires_user_write_approval(tool_name, registry)
        result.outcome_kind = "connector_tool_proposal"
        result.tool_name = tool_name
        result.tool_invoke_action = invoke or None
        result.tool_arguments = args
        result.requires_write_approval = bool(requires_write)
        if content:
            result.user_message = finalize_user_facing_message(
                content, context="unified_turn_shadow_tool_preamble"
            )
        return result

    if not content:
        result.outcome_kind = "error"
        result.error = "empty_model_response"
        return result

    safe = finalize_user_facing_message(content, context="unified_turn_shadow")
    try:
        assert_no_raw_catalog_action_keys(safe)
    except AssertionError as exc:
        result.outcome_kind = "error"
        result.error = str(exc)[:300]
        result.user_message = safe[:1200]
        return result

    lower = safe.lower()
    knowledge_boundary_markers = (
        "don't have that information",
        "do not have that information",
        "don't have that count",
        "do not have that count",
        "don't have visibility",
        "do not have visibility",
        "no visibility into",
        "wasn't retrieved",
        "was not retrieved",
        "not retrieved this turn",
        "can't report a",
        "cannot report a",
    )
    if any(marker in lower for marker in knowledge_boundary_markers):
        result.outcome_kind = "knowledge_boundary"
    elif "?" in safe and any(
        token in lower
        for token in ("which", "what ", "who ", "could you", "can you", "should i", "hold or", "abandon")
    ):
        result.outcome_kind = "clarifying_question"
    elif any(token in lower for token in ("approve", "confirm", "go ahead", "should i send", "proceed")):
        result.outcome_kind = "confirmation_request"
    else:
        result.outcome_kind = "conversational_reply"
    result.user_message = safe
    return result


def emit_unified_turn_shadow_audit(
    *,
    client: Any,
    org_id: str,
    actor_id: str,
    conversation_id: str | None,
    result: UnifiedTurnShadowResult,
) -> None:
    if client is None or not org_id or result.outcome_kind == "skipped":
        return
    try:
        from app.workflows.audit import write_audit_event

        action = (
            "unified_turn.live.completed"
            if result.live_served
            else "unified_turn.shadow.completed"
        )
        write_audit_event(
            client,
            org_id,
            actor_id or org_id,
            action,
            "conversation",
            conversation_id or org_id,
            result.to_audit_payload(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("unified_turn shadow audit skipped: %s", exc)


async def apply_unified_turn_live(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    message: str,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    connected_integrations: list[str] | None,
    client: Any = None,
    settings: Settings | None = None,
    environment_name: str = "production",
) -> dict[str, Any] | None:
    """Phase 4: run unified turn and map to a stop_pipeline turn when safe.

    Returns None to fall through to the classical pipeline (rollback path).
    Write tool proposals stage ``awaiting_confirm`` — never bypass approval.
    """
    active = settings or get_settings()
    if not getattr(active, "unified_turn_live_enabled", False):
        return None

    result = await run_unified_turn_shadow(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=message,
        task_state=task_state,
        conversation_history=conversation_history,
        connected_integrations=connected_integrations,
        client=client,
        settings=active,
    )
    if result.outcome_kind in {"skipped", "error"}:
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return None

    text_kinds = {
        "conversational_reply",
        "clarifying_question",
        "knowledge_boundary",
        "confirmation_request",
    }
    if result.outcome_kind in text_kinds and (result.user_message or "").strip():
        result.live_served = True
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm" if result.outcome_kind == "confirmation_request" else "answer",
            "message": result.user_message,
            "task_state": task_state,
            "answer_explanation": f"Unified turn live ({result.outcome_kind})",
            "model": result.model or "unified_turn_live",
            "unified_outcome_kind": result.outcome_kind,
            "latency_ms": result.latency_ms,
            "first_token_ms": result.first_token_proxy_ms,
        }

    if result.outcome_kind == "connector_tool_proposal" and result.tool_name:
        from app.services.react_write_gate import plan_from_react_tool_call
        from app.services.tool_registry import get_tool_registry

        registry = get_tool_registry()
        plan = plan_from_react_tool_call(
            result.tool_name,
            result.tool_arguments,
            registry,
            requires_approval=bool(result.requires_write_approval),
        )
        if plan is None or not conversation_id:
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=result,
            )
            return None

        if plan.requires_approval or result.requires_write_approval:
            from app.services.chat_connector_execution_service import (
                ChatConnectorExecutionService,
                enrich_plan_inference_metadata,
            )
            from app.services.connector_action_workflows import format_write_approval_message
            from app.services.connector_parameter_inference import (
                ParameterInferenceContext,
                infer_missing_parameters,
            )
            from app.services.connector_session_state import load_connector_session
            from app.services.conversation_state_service import get_conversation_state_service

            plan = enrich_plan_inference_metadata(plan, message=message or "")
            plan = infer_missing_parameters(
                plan,
                ParameterInferenceContext(
                    message=message or "",
                    conversation_history=list((task_state or {}).get("recent_user_messages") or []),
                    task_state=task_state or {},
                    connector_session=load_connector_session(task_state or {}),
                    client=client,
                    org_id=org_id,
                    settings=active,
                    environment_name=environment_name,
                ),
            )
            pending_params = {
                **ChatConnectorExecutionService.plan_to_dict(plan),
                "status": "awaiting_confirm",
                "source": "unified_turn_live",
            }
            state = get_conversation_state_service(active)
            await state.update_task_state(
                conversation_id,
                org_id,
                {
                    "pending_task": {
                        "type": "connector_action",
                        "status": "awaiting_confirm",
                        "params": pending_params,
                    }
                },
                client=client,
            )
            refreshed = await state.get_task_state(conversation_id, org_id, client=client)
            confirm_message = format_write_approval_message(plan)
            if result.user_message:
                confirm_message = f"{result.user_message.strip()}\n\n{confirm_message}"
            result.live_served = True
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=result,
            )
            return {
                "stop_pipeline": True,
                "dialogue_mode": "confirm",
                "message": finalize_user_facing_message(
                    confirm_message, context="unified_turn_live_approval"
                ),
                "task_state": refreshed,
                "pending_task": (refreshed or {}).get("pending_task"),
                "answer_explanation": "Unified turn live (write approval)",
                "model": result.model or "unified_turn_live",
                "unified_outcome_kind": result.outcome_kind,
            }

        # Read tool proposals: fall through to classical governed execution (no bypass).
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return None

    emit_unified_turn_shadow_audit(
        client=client,
        org_id=org_id,
        actor_id=user_id,
        conversation_id=conversation_id,
        result=result,
    )
    return None


async def run_unified_turn_shadow_and_audit(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    message: str,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    connected_integrations: list[str] | None,
    client: Any = None,
    settings: Settings | None = None,
) -> None:
    result = await run_unified_turn_shadow(
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=message,
        task_state=task_state,
        conversation_history=conversation_history,
        connected_integrations=connected_integrations,
        client=client,
        settings=settings,
    )
    emit_unified_turn_shadow_audit(
        client=client,
        org_id=org_id,
        actor_id=user_id,
        conversation_id=conversation_id,
        result=result,
    )


def schedule_unified_turn_shadow(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    message: str,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    connected_integrations: list[str] | None,
    client: Any = None,
    settings: Settings | None = None,
) -> None:
    """Fire-and-forget shadow run (does not block the classical pipeline)."""
    active = settings or get_settings()
    # Live cutover already awaits the same call — avoid a duplicate shadow.
    if getattr(active, "unified_turn_live_enabled", False):
        return
    if not getattr(active, "unified_turn_shadow_enabled", False):
        return

    async def _runner() -> None:
        try:
            await run_unified_turn_shadow_and_audit(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                task_state=task_state,
                conversation_history=conversation_history,
                connected_integrations=connected_integrations,
                client=client,
                settings=active,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("unified_turn_shadow background task failed: %s", exc)

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_runner())
        _SHADOW_BACKGROUND_TASKS.add(task)
        task.add_done_callback(_SHADOW_BACKGROUND_TASKS.discard)
    except RuntimeError:
        asyncio.run(_runner())
