"""Single-call turn reasoning (shadow path) — replaces classify-then-route over time.

Phase 1: shadow only — one model call with conversation, pending context, and
narrowed native tool schemas. Does not execute tools or change user-visible output.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
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
from app.services.user_facing_copy_guard import assert_no_raw_catalog_action_keys, finalize_user_facing_message

logger = get_logger(__name__)

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
    first_token_proxy_ms: int | None = None  # completion latency until first usable content

    def to_audit_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["user_message"] = (self.user_message or "")[:1200]
        if self.tool_arguments:
            payload["tool_arguments"] = {
                k: str(v)[:200] for k, v in list(self.tool_arguments.items())[:20]
            }
        # Phase 1 dual-path markers: classical still serves the user; shadow never executes.
        payload["shadow_user_visible"] = False
        payload["classical_path_active"] = True
        payload["shadow_executes_tools"] = False
        return payload


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


def _resolve_model(settings: Settings) -> str:
    from app.config import MODEL_TIERS

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
    """One model call; does not execute tools or return to the user."""
    active = settings or get_settings()
    if not getattr(active, "unified_turn_shadow_enabled", False):
        return UnifiedTurnShadowResult(outcome_kind="skipped")

    if not (active.openai_api_key or "").strip():
        return UnifiedTurnShadowResult(outcome_kind="error", error="openai_not_configured")

    start = time.perf_counter()
    registry = get_tool_registry()
    permitted = ["*"]
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    all_tools = registry.get_tools_for_agent(permitted, connected)
    visible, tool_stats = narrow_tools_for_turn(
        all_tools,
        query=message,
        connected_integrations=connected,
        requires_action=None,
        max_tools=int(getattr(active, "unified_turn_shadow_max_tools", 32) or 32),
    )

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

    model = _resolve_model(active)
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

    try:
        response = await openai_client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("unified_turn_shadow model call failed: %s", exc)
        return UnifiedTurnShadowResult(
            outcome_kind="error",
            error=str(exc)[:500],
            latency_ms=int((time.perf_counter() - start) * 1000),
            tool_stats=tool_stats,
            model=model,
        )

    choice = response.choices[0].message
    content = (choice.content or "").strip()
    tool_calls = choice.tool_calls or []
    latency_ms = int((time.perf_counter() - start) * 1000)

    result = UnifiedTurnShadowResult(
        latency_ms=latency_ms,
        first_token_proxy_ms=latency_ms,  # non-streaming shadow; Phase 3 upgrades to true TTFT
        tool_stats=tool_stats,
        model=model,
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

        write_audit_event(
            client,
            org_id,
            actor_id or org_id,
            "unified_turn.shadow.completed",
            "conversation",
            conversation_id or org_id,
            result.to_audit_payload(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("unified_turn shadow audit skipped: %s", exc)


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
        loop.create_task(_runner())
    except RuntimeError:
        asyncio.run(_runner())
