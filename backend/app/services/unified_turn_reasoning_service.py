"""Single-call turn reasoning (shadow path) — replaces classify-then-route over time.

Phase 1: shadow only — one model call with conversation, pending context, and
narrowed native tool schemas. Does not execute tools or change user-visible output.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from typing import Any, Literal

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.gravitre_voice import apply_voice, voice_system_prompt_section
from app.services.model_router import get_model_router
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
from app.services.providers.openai_adapter import _supports_custom_temperature
from app.services.react_write_gate import (
    resolve_user_write_approval_required,
    tool_requires_user_write_approval,
)
from app.services.tool_registry import get_tool_registry
from app.services.unified_turn_pending_context import build_unified_turn_pending_context
from app.services.unified_turn_tool_retrieval import (
    embed_narrow_tools_for_turn,
    is_task_shaped_for_retrieval,
)
from app.services.user_facing_copy_guard import assert_no_raw_catalog_action_keys, finalize_user_facing_message
from app.core.safe_dict import safe_normalize_stored_dict

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
    # R1: why LIVE returned None (intentional tool defer vs error). Empty when served.
    fallthrough_reason: str | None = None
    # F2: structured defer signal from LIVE reasoning (not bare vendor keyword match).
    needs_tool_sse: bool = False
    # Org connector inventory snapshot at turn time (audit/debug).
    connected_integrations: list[str] = field(default_factory=list)
    qa_force_tool: str | None = None
    qa_overrode_model_tool: str | None = None
    qa_force_outcome: str | None = None

    def to_audit_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["user_message"] = (self.user_message or "")[:1200]
        if self.tool_arguments:
            payload["tool_arguments"] = {
                k: str(v)[:200] for k, v in list(self.tool_arguments.items())[:20]
            }
        if self.connected_integrations:
            payload["connected_integrations"] = list(self.connected_integrations)
        live = bool(self.live_served)
        payload["shadow_user_visible"] = live
        payload["classical_path_active"] = not live
        payload["shadow_executes_tools"] = False  # tools still go through write/execute gates
        if self.fallthrough_reason:
            payload["fallthrough_reason"] = self.fallthrough_reason
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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


async def _complete_unified_turn_stream(
    openai_client: Any,
    *,
    kwargs: dict[str, Any],
    wall_start: float,
    model_start: float,
    timeout_s: float = 20.0,
) -> _StreamedCompletion:
    """Stream the shadow completion; record wall TTFT and model-only TTFT."""

    async def _run() -> _StreamedCompletion:
        stream_kwargs = {
            **kwargs,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        content_parts: list[str] = []
        tool_acc: dict[int, dict[str, Any]] = {}
        first_token_ms: int | None = None
        model_ttft_ms: int | None = None
        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0

        stream = await openai_client.chat.completions.create(**stream_kwargs)
        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                details = getattr(usage, "prompt_tokens_details", None)
                if details is not None:
                    cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)
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
                            str(slot["function"].get("arguments") or "")
                            + str(fn.arguments or "")
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
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
        )

    cap = max(5.0, float(timeout_s or 20.0))
    try:
        return await asyncio.wait_for(_run(), timeout=cap)
    except asyncio.TimeoutError as exc:
        logger.warning("unified_turn_stream_timeout timeout_s=%s", cap)
        raise TimeoutError(f"unified_turn_stream_timeout:{cap}") from exc


async def _complete_unified_turn(
    router: Any,
    openai_client: Any,
    *,
    model: str,
    kwargs: dict[str, Any],
    wall_start: float,
    model_start: float,
    timeout_s: float = 20.0,
) -> _StreamedCompletion:
    """Dispatch tool completion to the agent's configured provider."""
    from app.services.providers.provider_tool_router import (
        complete_with_tools,
        resolve_provider_for_model,
    )

    provider = resolve_provider_for_model(model)
    if provider == "openai":
        return await _complete_unified_turn_stream(
            openai_client,
            kwargs=kwargs,
            wall_start=wall_start,
            model_start=model_start,
            timeout_s=timeout_s,
        )

    cap = max(5.0, float(timeout_s or 20.0))

    async def _run() -> _StreamedCompletion:
        resp = await complete_with_tools(
            router,
            model=model,
            messages=list(kwargs.get("messages") or []),
            tools=kwargs.get("tools") or [],
            tool_choice=str(kwargs.get("tool_choice") or "auto"),
            temperature=kwargs.get("temperature"),
        )
        choice = resp.choices[0]
        message = choice.message
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        content = (getattr(message, "content", None) or "").strip()
        end = time.perf_counter()
        latency_ms = int((end - wall_start) * 1000)
        model_total_ms = int((end - model_start) * 1000)
        return _StreamedCompletion(
            content=content,
            tool_calls=tool_calls,
            first_token_ms=latency_ms,
            model_ttft_ms=model_total_ms,
            latency_ms=latency_ms,
            model_total_ms=model_total_ms,
            streamed=False,
        )

    try:
        return await asyncio.wait_for(_run(), timeout=cap)
    except asyncio.TimeoutError as exc:
        logger.warning("unified_turn_provider_timeout timeout_s=%s provider=%s", cap, provider)
        raise TimeoutError(f"unified_turn_provider_timeout:{cap}") from exc


def _stable_tool_list(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable ordering so OpenAI automatic prefix caching can hit across turns."""
    from app.services.narrowed_tools import NarrowedTools, mark_narrowed

    def _name(tool: dict[str, Any]) -> str:
        fn = tool.get("function")
        if isinstance(fn, dict):
            return str(fn.get("name") or "")
        return str(tool.get("name") or "")

    ordered = sorted(tools, key=_name)
    if isinstance(tools, NarrowedTools) or getattr(tools, "gravitre_narrowed", False):
        return mark_narrowed(
            ordered,
            stats=getattr(tools, "stats", None),
            source=str(getattr(tools, "source", "") or "narrow_tools_for_turn"),
        )
    return ordered


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


_REMIND_ME_RE = re.compile(
    r"(?i)\b(remind me|what did we (just )?(decide|pick|choose)|"
    r"did we (pick|decide|choose)|which .+ did (we|i)|"
    r"without asking( me)? again|did i correct|which .+ (did i|was my) correct|"
    r"after my correction|which (market|segment|geo|cloud|law|city|hq)\b)"
)

_USER_CORRECTION_RE = re.compile(
    r"(?i)\b(correction\b|standing( from now on)?\b|forget \w+|we ARE\b|"
    r"actually\b.{0,40}\bnot\b|primary (market|cloud|geo|focus) is\b|"
    r"governing law is\b|hq is\b|hiring geo is\b)"
)


def _is_remind_me_turn(message: str | None) -> bool:
    return bool(_REMIND_ME_RE.search((message or "").strip()))


def _prior_recommendations_block(
    conversation_history: list[dict[str, Any]] | None,
) -> str:
    """Surface recent assistant recommendations for remind-me turns (anti-invert)."""
    prior: list[str] = []
    for row in list(conversation_history or []):
        if str(row.get("role") or "").lower() != "assistant":
            continue
        text = str(row.get("content") or row.get("message") or "").strip()
        if text:
            prior.append(text[:500])
    if not prior:
        return ""
    body = "\n---\n".join(prior[-4:])
    return (
        "PRIOR ASSISTANT RECOMMENDATIONS IN THIS THREAD "
        "(authoritative for remind-me / what-did-we-decide — restate these; "
        "do not invert or replace with a generic industry default):\n"
        + body
    )


def _standing_user_corrections_block(
    conversation_history: list[dict[str, Any]] | None,
) -> str:
    """Surface user corrections as standing facts for later turns (rule 6)."""
    hits: list[str] = []
    for row in list(conversation_history or []):
        if str(row.get("role") or "").lower() != "user":
            continue
        text = str(row.get("content") or row.get("message") or "").strip()
        if not text:
            continue
        if _USER_CORRECTION_RE.search(text):
            hits.append(text[:400])
    if not hits:
        return ""
    body = "\n---\n".join(hits[-6:])
    return (
        "STANDING USER CORRECTIONS IN THIS THREAD "
        "(authoritative ground truth for the rest of the conversation — "
        "when entries conflict, the LATEST correction wins; "
        "apply that value; never claim it was unspecified; never revert "
        "to the pre-correction value):\n"
        + body
    )


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


def _resolve_unified_turn_model(
    settings: Settings,
    *,
    agent: dict[str, Any] | None,
    task_shaped: bool = False,
) -> str:
    """Honor agent-configured model for unified-turn tool calling when set."""
    if agent:
        configured = str(agent.get("model") or "").strip()
        if configured:
            return configured
    return _resolve_model(settings, task_shaped=task_shaped)


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
    qa_force_tool: str | None = None,
    qa_force_outcome: str | None = None,
    agent: dict[str, Any] | None = None,
    permitted_tools: list[str] | None = None,
    spoken_mode: bool = False,
    classification: dict[str, Any] | None = None,
    research_scope: str | None = None,
    cognitive_context: Any | None = None,
) -> UnifiedTurnShadowResult:
    """One model call; does not execute tools (Phase 4 may serve text to the user)."""
    active = settings or get_settings()
    shadow_on = bool(getattr(active, "unified_turn_shadow_enabled", False))
    live_on = bool(getattr(active, "unified_turn_live_enabled", False))
    if not shadow_on and not live_on:
        return UnifiedTurnShadowResult(outcome_kind="skipped")

    from app.services.providers.provider_tool_router import (
        provider_tools_configured,
        resolve_provider_for_model,
    )

    probe_model = _resolve_unified_turn_model(active, agent=agent, task_shaped=False)
    probe_provider = resolve_provider_for_model(probe_model)
    if not provider_tools_configured(probe_provider, active):
        return UnifiedTurnShadowResult(
            outcome_kind="error",
            error=f"{probe_provider}_not_configured",
        )

    from app.services.unified_turn_qa_hooks import (
        resolve_qa_force_outcome,
        synthetic_qa_outcome,
    )

    forced_outcome = resolve_qa_force_outcome(active, header_value=qa_force_outcome)
    if forced_outcome:
        synth = synthetic_qa_outcome(forced_outcome, message=message or "")
        return UnifiedTurnShadowResult(
            outcome_kind=synth["outcome_kind"],  # type: ignore[arg-type]
            user_message=synth["user_message"],
            qa_force_outcome=forced_outcome,
            connected_integrations=list(connected_integrations or []),
        )

    wall_start = time.perf_counter()
    registry = get_tool_registry()
    from app.operators.react_engine import resolve_permitted_tools

    # Phase 1: custom/department agents must not receive the full org catalog when
    # their row scopes tools/systems — same resolve_permitted_tools as classical ReAct.
    permitted = resolve_permitted_tools(agent, permitted_tools)
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    if "platform" not in connected:
        connected.append("platform")
    all_tools = registry.get_tools_for_agent(permitted, connected)
    t_after_registry = time.perf_counter()

    use_embed, shape_label, retrieval_query = is_task_shaped_for_retrieval(message or "")
    embed_flag = bool(getattr(active, "unified_turn_embedding_tool_retrieval", True))
    min_catalog = int(getattr(active, "unified_turn_embed_min_catalog_tools", 40) or 40)
    catalog_large_enough = len(all_tools) >= min_catalog
    embed_on = embed_flag and use_embed and catalog_large_enough
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
            query=retrieval_query or message,
            connected_integrations=connected,
            requires_action=None,
            max_tools=max_tools,
        )
        skip_reason = None
        if embed_flag and use_embed and not catalog_large_enough:
            skip_reason = f"catalog_below_embed_min:{len(all_tools)}<{min_catalog}"
        tool_stats = {
            **(tool_stats or {}),
            "retrievalMethod": "keyword_narrow_tools_for_turn",
            "embeddingToolRetrieval": False,
            "embeddingSkippedReason": skip_reason,
        }
    visible = _stable_tool_list(list(visible or []))
    t_after_narrow = time.perf_counter()

    # G.5.2 progressive disclosure — stubs + search_catalog_tools (A1/A2).
    # Candidate set stays the narrowed list; full schemas load on demand.
    from app.services.narrowed_tools import NarrowedTools, assert_tools_narrowed, mark_narrowed
    from app.services.progressive_tool_schemas import (
        SEARCH_CATALOG_TOOLS_NAME,
        apply_progressive_disclosure,
        execute_search_catalog_tools,
        gate_deferred_tool_call,
        is_search_catalog_tools,
        payload_bytes,
        select_progressive_preload_names,
    )

    progressive_on = bool(getattr(active, "unified_turn_progressive_schemas", True))
    full_by_name: dict[str, dict[str, Any]] = {}
    loaded_names: set[str] = set()
    full_narrowed_bytes = payload_bytes(list(visible or []))
    attach_tools = visible
    if progressive_on and visible:
        preload_n = int(getattr(active, "unified_turn_progressive_preload_top", 2) or 0)
        min_sim = float(
            getattr(active, "unified_turn_progressive_preload_min_similarity", 0.2) or 0.2
        )
        top_sim = (tool_stats or {}).get("topSimilarity")
        preload_ok = preload_n > 0 and (
            top_sim is None or (isinstance(top_sim, (int, float)) and float(top_sim) >= min_sim)
        )
        focused = (tool_stats or {}).get("focusedConnectors") or []
        if not isinstance(focused, list):
            focused = []
        preload_names = (
            set(
                select_progressive_preload_names(
                    list(visible),
                    max_preload=preload_n,
                    focused_connectors=[str(c) for c in focused],
                )
            )
            if preload_ok
            else set()
        )
        attach_tools, full_by_name, loaded_names = apply_progressive_disclosure(
            list(visible), loaded_names=preload_names
        )
        tool_stats = {
            **(tool_stats or {}),
            **(getattr(attach_tools, "stats", None) or {}),
            "progressiveDisclosure": True,
            "progressivePreloaded": sorted(preload_names),
            "fullNarrowedPayloadBytes": full_narrowed_bytes,
            "progressivePayloadBytes": payload_bytes(list(attach_tools)),
        }
    else:
        attach_tools = mark_narrowed(
            list(visible or []),
            stats=tool_stats,
            source=str((tool_stats or {}).get("retrievalMethod") or "narrow_tools_for_turn"),
        )
        tool_stats = {**(tool_stats or {}), "progressiveDisclosure": False}

    pending_block = build_unified_turn_pending_context(
        task_state,
        last_assistant_message=_last_assistant_snippet(conversation_history),
    )
    from app.services.conversational_reply_service import build_capability_snapshot

    capability_block = build_capability_snapshot(
        connected_integrations=connected,
        client=client,
        org_id=org_id,
    )
    # Full Module D spec is the system instruction (not a post-hoc phrase bank).
    # spoken_mode stacks Register 5 (SPOKEN); agent injects self-recognition by name.
    system = apply_voice(
        build_module_d_unified_system_prompt(
            extra_operator_rules=voice_system_prompt_section(),
            spoken_mode=bool(spoken_mode),
            agent=agent,
        )
    )
    user_parts = []
    if pending_block:
        user_parts.append(pending_block)
    else:
        user_parts.append(
            "NO PENDING STATE this turn. Do not mention abandon/hold or a pending item."
        )
    user_parts.append(
        "CONNECTED INTEGRATIONS THIS ORG (authoritative for this turn — do not claim "
        "a listed vendor is disconnected without calling assistant_connector_status):\n"
        + capability_block
    )
    from app.services.chat_write_intent import build_gmail_write_intent_prompt_section

    intent_hint = build_gmail_write_intent_prompt_section(message or "")
    if intent_hint:
        user_parts.append(intent_hint)
    # Explicit tool inventory note for knowledge-boundary honesty.
    if attach_tools:
        names = sorted(
            {
                str(t.get("function", {}).get("name") or t.get("name") or "")
                for t in attach_tools
                if isinstance(t, dict)
            }
        )
        names = [n for n in names if n and n != SEARCH_CATALOG_TOOLS_NAME][:40]
        if progressive_on:
            loaded_note = ""
            if loaded_names:
                loaded_note = (
                    f" Full schemas already loaded for: {', '.join(sorted(loaded_names))}. "
                    f"Call {SEARCH_CATALOG_TOOLS_NAME} only if you need another tool's parameters."
                )
            else:
                loaded_note = (
                    f" Stubs are name + description only; call {SEARCH_CATALOG_TOOLS_NAME} "
                    "to load full parameters before invoking a connector tool."
                )
            user_parts.append(
                "AVAILABLE TOOLS THIS TURN "
                f"({loaded_note.strip()} You have NO other live data sources):\n- "
                + "\n- ".join(names)
            )
        else:
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
    remind_me = _is_remind_me_turn(message)
    standing = _standing_user_corrections_block(conversation_history)
    if standing:
        user_parts.append(standing)
    prior_recs = _prior_recommendations_block(conversation_history) if remind_me else ""
    if prior_recs:
        user_parts.append(prior_recs)

    if client is not None and org_id and not remind_me:
        from app.services.unified_turn_knowledge_context import (
            build_unified_turn_knowledge_context,
        )
        from app.services.agent_knowledge_assignment_service import (
            AgentKnowledgeAssignmentService,
        )

        knowledge_assignments: list[dict[str, Any]] = []
        agent_id = str((agent or {}).get("id") or "")
        if agent_id and agent_id not in {"assistant"}:
            try:
                knowledge_assignments = AgentKnowledgeAssignmentService(
                    active
                ).list_assignments(client, org_id, agent_id)
            except Exception:  # noqa: BLE001
                knowledge_assignments = AgentKnowledgeAssignmentService(
                    active
                ).resolve_assignments(agent or {})
        knowledge_block, knowledge_meta = await build_unified_turn_knowledge_context(
            org_id=org_id,
            query=message or "",
            client=client,
            settings=active,
            classification=classification,
            agent=agent,
            knowledge_assignments=knowledge_assignments,
            research_scope=research_scope,
        )
        if knowledge_block:
            user_parts.append(knowledge_block)
        unified_turn_knowledge_meta = knowledge_meta if knowledge_meta else None
    else:
        unified_turn_knowledge_meta = (
            {"skipped": "remind_me_turn"} if remind_me else None
        )
    # Kernel RECALL/KNOWLEDGE pack (post-retrieve, pre-ACT) — denser than LIVE-only KF.
    if cognitive_context is not None and not remind_me:
        try:
            from app.services.cognitive_turn_kernel import to_prompt_sections

            sections = to_prompt_sections(cognitive_context)
            mem = (sections.get("memory_section") or "").strip()
            know = (sections.get("knowledge_section") or "").strip()
            bias = (sections.get("outcome_bias_section") or "").strip()
            if mem:
                user_parts.append(mem)
            if know:
                user_parts.append(know)
            if bias:
                user_parts.append(bias)
            if isinstance(unified_turn_knowledge_meta, dict):
                unified_turn_knowledge_meta = {
                    **unified_turn_knowledge_meta,
                    "cognitiveTurnId": getattr(cognitive_context, "turn_id", None),
                    "outcomeBiasInjected": bool(bias),
                }
            elif mem or know or bias:
                unified_turn_knowledge_meta = {
                    "cognitiveTurnId": getattr(cognitive_context, "turn_id", None),
                    "outcomeBiasInjected": bool(bias),
                }
        except Exception:  # noqa: BLE001
            pass
    user_parts.append(f"USER MESSAGE:\n{(message or '').strip()}")
    user_content = "\n\n".join(user_parts)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(_history_to_messages(conversation_history))
    messages.append({"role": "user", "content": user_content})
    t_after_prompt = time.perf_counter()

    tools_payload_bytes = payload_bytes(list(attach_tools or []))
    messages_chars = sum(len(str(m.get("content") or "")) for m in messages)
    system_prompt_chars = len(system or "")
    # Hypothetical full-catalog payload for the same connected set (not sent).
    full_catalog_bytes = len(json.dumps(all_tools, separators=(",", ":")).encode("utf-8"))

    model = _resolve_unified_turn_model(active, agent=agent, task_shaped=use_embed)
    router = get_model_router()
    from app.services.providers.provider_tool_router import resolve_provider_for_model

    inference_provider = resolve_provider_for_model(model)
    openai_client = router._openai if inference_provider == "openai" else None  # noqa: SLF001
    if inference_provider == "openai" and openai_client is None:
        return UnifiedTurnShadowResult(outcome_kind="error", error="openai_client_unavailable")

    assert_tools_narrowed(attach_tools, where="unified_turn_reasoning_service.attach")

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
        "full_narrowed_payload_bytes": full_narrowed_bytes,
        "progressive_disclosure": progressive_on,
        "system_prompt_chars": system_prompt_chars,
        "messages_chars": messages_chars,
        "total_tools": len(all_tools),
        "visible_tools": len(
            [
                t
                for t in (attach_tools or [])
                if str((t.get("function") or {}).get("name") or "") != SEARCH_CATALOG_TOOLS_NAME
            ]
        )
        if progressive_on
        else len(visible),
        "max_tools_cap": max_tools,
        "retrieval_method": retrieval_method,
        "embedding_tool_retrieval": embedding_used,
        "turn_shape_hint": shape_label,
        "retrieval_query": (retrieval_query or "")[:240],
        "task_model_tier": str(getattr(active, "unified_turn_task_model_tier", "") or "") or None,
    }
    if unified_turn_knowledge_meta:
        breakdown["unifiedTurnKnowledge"] = unified_turn_knowledge_meta
    for _embed_key in (
        "embed_query_ms",
        "embed_query_method",
        "embed_query_provider",
        "embed_query_cache_hit",
        "embed_query_cache_lookup_ms",
        "embed_query_encode_ms",
        "embed_query_model",
        "embed_tool_docs_ms",
        "embed_tool_doc_provider",
        "embed_tool_doc_cache_hits",
        "embed_tool_doc_cache_misses",
        "embed_tool_doc_batch_api_calls",
        "embed_tool_doc_cache_lookup_ms",
        "embed_similarity_rank_ms",
        "embed_narrow_total_ms",
        "embeddingCandidateCount",
        "topSimilarity",
    ):
        if _embed_key in (tool_stats or {}):
            breakdown[_embed_key] = tool_stats[_embed_key]
    tool_stats = {
        **(tool_stats or {}),
        "toolsPayloadBytes": tools_payload_bytes,
        "fullCatalogPayloadBytes": full_catalog_bytes,
        "fullNarrowedPayloadBytes": full_narrowed_bytes,
        "turnShapeHint": shape_label,
    }

    completion = None
    content = ""
    tool_calls: list[Any] = []
    try:
        model_start = time.perf_counter()
        breakdown["openai_create_schedule_ms"] = int((model_start - t_after_prompt) * 1000)
        stream_timeout_s = float(getattr(active, "unified_turn_stream_timeout_s", 20.0) or 20.0)
        breakdown["stream_timeout_s"] = stream_timeout_s
        if loaded_names:
            breakdown["progressive_preloaded"] = sorted(loaded_names)
            breakdown["progressive_loaded_count"] = len(loaded_names)
        progressive_round_ms: list[int] = []
        # Up to 2 rounds: search_catalog_tools may load full schemas then continue.
        for prog_round in range(2):
            from app.services.narrowed_tools import openai_tool_payload

            # Pure conversational / human-moment venting: never attach tools.
            # Empathy-warranting turns must not derail into connector calls (rule 10).
            conversational_no_tools = shape_label == "conversational"
            if conversational_no_tools:
                round_tools: list[dict[str, Any]] = []
            elif isinstance(attach_tools, NarrowedTools):
                round_tools = attach_tools
            else:
                round_tools = list(attach_tools or [])
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "tool_choice": "none" if conversational_no_tools else "auto",
            }
            if round_tools:
                kwargs["tools"] = [openai_tool_payload(t) for t in round_tools]
            if _supports_custom_temperature(model):
                kwargs["temperature"] = 0.2
            assert_tools_narrowed(round_tools, where=f"unified_turn.round_{prog_round}")
            if conversational_no_tools:
                breakdown["conversational_no_tools"] = True
            round_start = time.perf_counter()
            completion = await _complete_unified_turn(
                router,
                openai_client,
                model=model,
                kwargs=kwargs,
                wall_start=wall_start,
                model_start=model_start if prog_round == 0 else time.perf_counter(),
                timeout_s=stream_timeout_s,
            )
            progressive_round_ms.append(int((time.perf_counter() - round_start) * 1000))
            breakdown["progressive_round_ms"] = list(progressive_round_ms)
            content = completion.content
            tool_calls = list(completion.tool_calls or [])
            if (
                progressive_on
                and tool_calls
                and is_search_catalog_tools(str(tool_calls[0].function.name or ""))
            ):
                args: dict[str, Any] = {}
                try:
                    parsed = json.loads(tool_calls[0].function.arguments or "{}")
                    if isinstance(parsed, dict):
                        args = parsed
                except json.JSONDecodeError:
                    args = {}
                loaded_names, search_result = execute_search_catalog_tools(
                    args, full_by_name=full_by_name, loaded_names=loaded_names
                )
                attach_tools, full_by_name, loaded_names = apply_progressive_disclosure(
                    list(visible), loaded_names=loaded_names
                )
                tool_stats = {
                    **(tool_stats or {}),
                    **(getattr(attach_tools, "stats", None) or {}),
                    "progressiveSearchRounds": prog_round + 1,
                    "progressiveLoaded": sorted(loaded_names),
                }
                breakdown["progressive_payload_bytes"] = payload_bytes(list(attach_tools))
                breakdown["progressive_loaded_count"] = len(loaded_names)
                # Feed search result back into the conversation for the next round.
                messages.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": [
                            {
                                "id": getattr(tool_calls[0], "id", None) or "search_1",
                                "type": "function",
                                "function": {
                                    "name": SEARCH_CATALOG_TOOLS_NAME,
                                    "arguments": tool_calls[0].function.arguments or "{}",
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": getattr(tool_calls[0], "id", None) or "search_1",
                        "content": json.dumps(search_result),
                    }
                )
                continue
            break
    except Exception as exc:  # noqa: BLE001
        logger.warning("unified_turn_shadow model call failed: %s", exc)
        breakdown["error"] = str(exc)[:200]
        if "unified_turn_stream_timeout" in str(exc):
            breakdown["stream_timed_out"] = True
        return UnifiedTurnShadowResult(
            outcome_kind="error",
            error=str(exc)[:500],
            latency_ms=int((time.perf_counter() - wall_start) * 1000),
            tool_stats=tool_stats,
            model=model,
            latency_breakdown=breakdown,
        )

    if completion is None:
        return UnifiedTurnShadowResult(
            outcome_kind="error",
            error="no_model_completion",
            latency_ms=int((time.perf_counter() - wall_start) * 1000),
            tool_stats=tool_stats,
            model=model,
            latency_breakdown=breakdown,
        )

    latency_ms = completion.latency_ms
    breakdown["model_ttft_ms"] = completion.model_ttft_ms
    breakdown["model_total_ms"] = completion.model_total_ms
    breakdown["wall_to_first_token_ms"] = completion.first_token_ms
    breakdown["prompt_tokens"] = completion.prompt_tokens
    breakdown["completion_tokens"] = completion.completion_tokens
    breakdown["cached_prompt_tokens"] = completion.cached_tokens
    if completion.prompt_tokens:
        breakdown["cached_prompt_ratio"] = round(
            completion.cached_tokens / max(1, completion.prompt_tokens),
            4,
        )
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
        connected_integrations=list(connected),
    )

    from app.services.unified_turn_qa_hooks import (
        registry_tool_for_force,
        resolve_qa_force_tool,
    )

    forced = resolve_qa_force_tool(active, header_value=qa_force_tool)
    if tool_calls or forced:
        if forced:
            try:
                tool_name, invoke, args = registry_tool_for_force(registry, forced)
            except ValueError as exc:
                result.outcome_kind = "error"
                result.error = str(exc)[:500]
                return result
            result.qa_force_tool = forced
            if tool_calls:
                result.qa_overrode_model_tool = str(tool_calls[0].function.name or "")
                try:
                    parsed = json.loads(tool_calls[0].function.arguments or "{}")
                    if isinstance(parsed, dict) and parsed:
                        args = parsed
                except json.JSONDecodeError:
                    pass
            # QA force loads the schema so progressive gate does not block fixtures.
            if tool_name:
                loaded_names.add(tool_name)
        else:
            tc = tool_calls[0]
            tool_name = str(tc.function.name or "")
            args = {}
            try:
                parsed = json.loads(tc.function.arguments or "{}")
                if isinstance(parsed, dict):
                    args = parsed
            except json.JSONDecodeError:
                args = {}
            if is_search_catalog_tools(tool_name):
                # Exhausted progressive rounds without a connector tool.
                result.outcome_kind = "clarifying_question"
                result.user_message = (
                    "I loaded catalog schemas but still need a specific action. "
                    "Which connector action should I take?"
                )
                return result
            if progressive_on and full_by_name:
                allowed, gate_reason = gate_deferred_tool_call(
                    tool_name,
                    loaded_names=loaded_names,
                    full_by_name=full_by_name,
                )
                if not allowed:
                    result.outcome_kind = "clarifying_question"
                    result.user_message = (
                        f"I need the full schema for `{tool_name}` before I can run it "
                        f"(progressive disclosure: {gate_reason}). "
                        f"Ask me again and I'll load parameters via {SEARCH_CATALOG_TOOLS_NAME} first."
                    )
                    breakdown["progressive_gate_blocked"] = gate_reason
                    return result
        spec = registry._specs.get(tool_name)  # noqa: SLF001
        invoke = str(getattr(spec, "invoke_action", "") or "") if spec else ""
        from app.capability_ontology.tool_bridge import is_capability_tool_name

        if is_capability_tool_name(tool_name):
            _, resolved_invoke, *_ = tool_requires_user_write_approval(
                tool_name,
                registry,
                connected_integrations=connected,
                query=message or "",
                classification=classification,
                args=args,
            )
            if resolved_invoke:
                invoke = resolved_invoke
        from app.services.chat_write_intent import evaluate_connector_tool_proposal

        review = evaluate_connector_tool_proposal(
            message=message or "",
            tool_name=tool_name,
            invoke_action=invoke or None,
            args=args,
        )
        if review.action == "clarify":
            result.outcome_kind = "clarifying_question"
            result.user_message = review.clarify_message
            if content and not forced:
                result.user_message = f"{content.strip()}\n\n{review.clarify_message}"
            return result
        tool_name = review.tool_name or tool_name
        invoke = review.invoke_action or invoke
        args = review.tool_arguments or args
        spec = registry._specs.get(tool_name)  # noqa: SLF001
        # HARD: write authority AFTER full schema load / selection (unchanged gate).
        requires_write, resolved_invoke, *_ = tool_requires_user_write_approval(
            tool_name,
            registry,
            connected_integrations=connected,
            query=message or "",
            classification=classification,
            args=args,
        )
        if not invoke and resolved_invoke:
            invoke = resolved_invoke
        requires_user_approval = False
        if requires_write and client is not None:
            requires_user_approval, *_ = resolve_user_write_approval_required(
                client,
                org_id,
                user_id,
                tool_name,
                registry,
                settings=active,
            )
        result.outcome_kind = "connector_tool_proposal"
        result.needs_tool_sse = True
        result.tool_name = tool_name
        result.tool_invoke_action = invoke or None
        result.tool_arguments = args
        result.requires_write_approval = bool(requires_user_approval)
        if content and not forced:
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
    if client is None or not org_id:
        return
    # Shadow-only skips stay quiet; LIVE fallthrough always emits (R1 metrics).
    if result.outcome_kind == "skipped" and not result.fallthrough_reason:
        return
    try:
        from app.workflows.audit import write_audit_event

        if result.live_served:
            action = "unified_turn.live.completed"
        elif result.fallthrough_reason:
            action = "unified_turn.live.fallthrough"
        else:
            action = "unified_turn.shadow.completed"
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


def _mark_live_fallthrough(
    result: UnifiedTurnShadowResult,
    reason: str,
) -> UnifiedTurnShadowResult:
    from app.services.unified_turn_fallthrough import assert_known_fallthrough_reason

    result.live_served = False
    result.fallthrough_reason = assert_known_fallthrough_reason(reason)
    return result


def _unified_live_turn_payload(
    result: UnifiedTurnShadowResult,
    task_state: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "stop_pipeline": True,
        "dialogue_mode": (
            "confirm"
            if result.outcome_kind == "confirmation_request"
            else "clarify"
            if result.outcome_kind == "clarifying_question"
            else "answer"
        ),
        "message": result.user_message,
        "task_state": task_state,
        "answer_explanation": f"Unified turn live ({result.outcome_kind})",
        "model": result.model or "unified_turn_live",
        "unified_outcome_kind": result.outcome_kind,
        "latency_ms": result.latency_ms,
        "first_token_ms": result.first_token_proxy_ms,
    }


async def _maybe_prepend_mixed_social_ack(
    *,
    message: str,
    body: str,
    task_state: dict[str, Any] | None,
    org_id: str,
    settings: Settings,
) -> str:
    """Port classical mixed-turn social ack onto LIVE-served copy."""
    from app.services.conversational_reply_service import generate_social_ack
    from app.services.conversational_turn_gate import classify_turn_shape
    from app.services.pending_reply_classifier import has_pending_family

    text = (body or "").strip()
    if not text or has_pending_family(task_state):
        return text
    turn_shape = await classify_turn_shape(
        message,
        settings=settings,
        org_id=org_id,
    )
    if turn_shape.shape != "mixed" or not (turn_shape.task_portion or "").strip():
        return text
    # Avoid double-acking when the model already opened with a social beat.
    if re.search(
        r"(?i)^\s*(ha\b|hey\b|noted|anytime|you're welcome|you are welcome|on it|sure[, ])",
        text,
    ):
        return text
    ack = (await generate_social_ack(
        turn_shape.social_portion or message,
        org_id=org_id,
        settings=settings,
    )).strip()
    if not ack:
        return text
    return f"{ack}\n\n{text}"


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
    mode_key: str | None = None,
    classification: dict[str, Any] | None = None,
    qa_force_tool: str | None = None,
    qa_force_outcome: str | None = None,
    agent: dict[str, Any] | None = None,
    permitted_tools: list[str] | None = None,
    agent_id: str | None = None,
    spoken_mode: bool = False,
    research_scope: str | None = None,
    cognitive_context: Any | None = None,
) -> dict[str, Any] | None:
    """Phase 4: run unified turn and map to a stop_pipeline turn when safe.

    Returns None to fall through to the classical pipeline (rollback path).
    Write tool proposals stage ``awaiting_confirm`` — never bypass approval.
    """
    active = settings or get_settings()
    if not getattr(active, "unified_turn_live_enabled", False):
        # Capstone: no silent handoff — emit when caller reached LIVE with a client.
        if client is not None and org_id:
            silent = UnifiedTurnShadowResult(
                outcome_kind="skipped",
                error="unified_turn_live_enabled=false",
                live_served=False,
            )
            _mark_live_fallthrough(silent, "live_disabled")
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=silent,
            )
        return None

    from app.services.unified_turn_pending_live import (
        resolve_unified_live_channel_override_reply,
        resolve_unified_live_meta_capability_reply,
        resolve_unified_live_pending_reply,
        unified_live_message_violates_no_pending_hold,
    )

    channel_result = await resolve_unified_live_channel_override_reply(
        message=message,
        task_state=task_state,
        org_id=org_id,
        client=client,
        conversation_id=conversation_id,
        settings=active,
    )
    if channel_result and (channel_result.user_message or "").strip():
        channel_result.live_served = True
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=channel_result,
        )
        updated_state = dict(task_state or {})
        clarified = safe_normalize_stored_dict(updated_state, key='clarified_params')
        from app.services.gravitre_voice import detect_channel_override_integration

        override = detect_channel_override_integration(message)
        if override:
            clarified["channel_override"] = override
            updated_state["clarified_params"] = clarified
            updated_state["preferred_connector"] = override
        payload = _unified_live_turn_payload(channel_result, updated_state)
        return payload

    meta_result = await resolve_unified_live_meta_capability_reply(
        message=message,
        task_state=task_state,
        org_id=org_id,
        connected_integrations=connected_integrations,
        client=client,
        settings=active,
    )
    if meta_result and (meta_result.user_message or "").strip():
        meta_result.live_served = True
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=meta_result,
        )
        return _unified_live_turn_payload(meta_result, task_state)

    pending_result = await resolve_unified_live_pending_reply(
        message=message,
        task_state=task_state,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        client=client,
        settings=active,
    )
    if pending_result and (pending_result.user_message or "").strip():
        pending_result.live_served = True
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=pending_result,
        )
        return _unified_live_turn_payload(pending_result, task_state)

    # confirm/reject/modify/slot_answer return None from the pending resolver so
    # classical Module B can execute them. Do not let shadow invent a yes/hold.
    # Previously this return was silent — fallthrough dashboards were blind to the
    # exact path that re-parsed compound subject/body and corrupted a live Gmail send.
    from app.services.pending_reply_classifier import has_pending_family

    if has_pending_family(task_state):
        pending = task_state.get("pending_task") if isinstance(task_state, dict) else None
        pending = pending if isinstance(pending, dict) else {}
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        silent = UnifiedTurnShadowResult(
            outcome_kind="skipped",
            user_message="",
            tool_invoke_action=str(params.get("invoke_action") or "").strip() or None,
            tool_stats={
                "pending_type": str(pending.get("type") or ""),
                "pending_status": str(pending.get("status") or ""),
            },
        )
        _mark_live_fallthrough(silent, "pending_family_classical_resume")
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=silent,
        )
        return None

    # F1 hard gate: retrieve-before-generate (pack-common / installed workflow /
    # ambiguous clarify). Runs before shadow + orch so classical never invents
    # steps when a retrieved plan exists.
    if conversation_id:
        from app.services.retrieve_plan_gate import (
            retrieve_plan_or_none,
            stage_retrieved_plan_turn,
        )

        retrieved = retrieve_plan_or_none(
            message or "",
            org_id=org_id,
            connected_integrations=list(connected_integrations or []),
            client=client,
            require_pack_install=True,  # F5: pack must be installed
        )
        if retrieved is not None:
            staged = await stage_retrieved_plan_turn(
                retrieved,
                org_id=org_id,
                conversation_id=conversation_id,
                message=message or "",
                task_state=task_state,
                client=client,
                settings=active,
            )
            audit = UnifiedTurnShadowResult(
                outcome_kind=str(  # type: ignore[arg-type]
                    staged.get("unified_outcome_kind") or "confirmation_request"
                ),
                user_message=str(staged.get("message") or ""),
                live_served=True,
                model="retrieve_plan_gate",
                connected_integrations=list(connected_integrations or []),
                needs_tool_sse=False,
            )
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=audit,
            )
            return staged

    from app.services.conversational_turn_gate import (
        ambiguous_open_clarify_reply,
        correction_recall_pushback_reply,
        definition_brief_reply,
        heuristic_turn_shape,
        is_human_moment_venting_no_ask,
    )
    from app.services.pending_reply_classifier import has_pending_family

    # Rule 1 hard path: known ambiguous opens must clarify first. Shared LIVE
    # path for every agent/surface — pattern list must include Legal/Cyber opens,
    # not only Marketing/Sales/HR/default.
    clarify_open = ambiguous_open_clarify_reply(message or "")
    if clarify_open and not has_pending_family(task_state):
        clarify_result = UnifiedTurnShadowResult(
            outcome_kind="clarifying_question",
            user_message=clarify_open,
            live_served=True,
            needs_tool_sse=False,
            model="ambiguous_open_clarify",
            connected_integrations=list(connected_integrations or []),
        )
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=clarify_result,
        )
        return _unified_live_turn_payload(clarify_result, task_state)

    # Rule 9 hard path: simple "what's X?" definitions stay brief prose (no
    # Handoff JSON / option dumps from department personas).
    definition_open = definition_brief_reply(message or "")
    if definition_open and not has_pending_family(task_state):
        definition_result = UnifiedTurnShadowResult(
            outcome_kind="conversational_reply",
            user_message=definition_open,
            live_served=True,
            needs_tool_sse=False,
            model="definition_brief",
            connected_integrations=list(connected_integrations or []),
        )
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=definition_result,
        )
        return _unified_live_turn_payload(definition_result, task_state)

    # Rules 6+7 hard path: standing-correction recall (+ optional Also: pushback)
    # before connector/identity derails ("which item / workflow / connector").
    recall_push = correction_recall_pushback_reply(
        message or "",
        conversation_history,
    )
    if recall_push and not has_pending_family(task_state):
        recall_result = UnifiedTurnShadowResult(
            outcome_kind="conversational_reply",
            user_message=recall_push,
            live_served=True,
            needs_tool_sse=False,
            model="correction_recall_pushback",
            connected_integrations=list(connected_integrations or []),
        )
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=recall_result,
        )
        return _unified_live_turn_payload(recall_result, task_state)

    # Rule 10 hard path: human-moment venting with no explicit ask must be served
    # as LIVE text without classical tool fallthrough (prevents HubSpot/Apollo derail).
    if is_human_moment_venting_no_ask(message or "") and not has_pending_family(task_state):
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
            qa_force_tool=None,
            qa_force_outcome=None,
            agent=agent,
            permitted_tools=permitted_tools,
            spoken_mode=bool(spoken_mode),
            classification=classification,
            research_scope=None,
            cognitive_context=cognitive_context,
        )
        text = (result.user_message or "").strip()
        if result.outcome_kind in {"skipped", "error"} or not text:
            from app.services.conversational_reply_service import generate_conversational_reply

            decision = heuristic_turn_shape(message or "")
            if decision is None or decision.shape != "conversational":
                from app.services.conversational_turn_gate import ConversationalGateDecision

                decision = ConversationalGateDecision(
                    shape="conversational",
                    reason="human_moment_venting_no_ask",
                    social_portion=(message or "").strip(),
                    category="venting",
                )
            text = await generate_conversational_reply(
                message or "",
                decision=decision,
                settings=active,
                org_id=org_id,
                task_state=task_state,
                conversation_history=conversation_history,
                connected_integrations=list(connected_integrations or []),
                client=client,
                allow_humor=False,
            )
            result.outcome_kind = "conversational_reply"
            result.user_message = text
            result.error = None
        result.needs_tool_sse = False
        result.live_served = True
        result.tool_name = None
        result.tool_invoke_action = None
        result.tool_arguments = None
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return _unified_live_turn_payload(result, task_state)

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
        qa_force_tool=qa_force_tool,
        qa_force_outcome=qa_force_outcome,
        agent=agent,
        permitted_tools=permitted_tools,
        spoken_mode=bool(spoken_mode),
        classification=classification,
        research_scope=research_scope,
        cognitive_context=cognitive_context,
    )
    if result.outcome_kind in {"skipped", "error"}:
        _mark_live_fallthrough(result, f"outcome_{result.outcome_kind}")
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return None

    # Pack-common intents must run BEFORE classical defer. The AI Chat TRY prompt
    # contains "Apollo" / "contact list", which match message_requires_classical_tool_sse
    # and used to fall through into a broken 2× Search-contacts orchestration.
    from app.services.pack_common_intent_defaults import (
        format_pack_common_msp_enrich_confirm_message,
        try_pack_common_list_create_plan,
        try_pack_common_msp_enrich_workflow_plan,
    )

    connected_for_pack = list(
        result.connected_integrations or connected_integrations or []
    )

    # Part 3 — pack-common list create: stage awaiting_confirm directly.
    pack_plan = try_pack_common_list_create_plan(
        message or "",
        connected_integrations=connected_for_pack,
    )
    if pack_plan is not None and conversation_id:
        from app.services.chat_connector_execution_service import (
            ChatConnectorExecutionService,
        )
        from app.services.connector_action_workflows import (
            format_write_approval_message,
            missing_params_stage_patch,
        )
        from app.services.conversation_state_service import get_conversation_state_service

        staged_missing = missing_params_stage_patch(
            pack_plan, message or "", task_state=task_state or {}
        )
        if not staged_missing:
            state = get_conversation_state_service(active)
            pending_params = {
                **ChatConnectorExecutionService.plan_to_dict(pack_plan),
                "status": "awaiting_confirm",
                "source": "pack_common_list_create",
            }
            await state.update_task_state(
                conversation_id,
                org_id,
                {
                    "pending_task": {
                        "type": "connector_action",
                        "status": "awaiting_confirm",
                        "params": pending_params,
                    },
                    "recent_user_messages": [message or ""],
                },
                client=client,
            )
            refreshed = await state.get_task_state(
                conversation_id, org_id, client=client
            )
            result.outcome_kind = "connector_tool_proposal"
            result.tool_name = pack_plan.tool_name
            result.tool_invoke_action = pack_plan.invoke_action
            result.tool_arguments = dict(pack_plan.args or {})
            result.requires_write_approval = True
            result.live_served = True
            result.model = f"{result.model or 'unified_turn'}+pack_common_list_create"
            result.user_message = format_write_approval_message(pack_plan)
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
                    result.user_message, context="unified_turn_live_pack_common_list"
                ),
                "task_state": refreshed,
                "pending_task": (refreshed or {}).get("pending_task"),
                "workflow_status": "awaiting_confirm",
                "answer_explanation": "Unified turn live (pack-common list create)",
                "model": result.model or "unified_turn_live",
                "unified_outcome_kind": "connector_tool_proposal",
            }

    # Part 3 — MSP Clay→HubSpot enrich: stage create_workflow confirm
    # (bare clay.crm.sync cannot approve-first; records are irreducible).
    enrich_plan = try_pack_common_msp_enrich_workflow_plan(
        message or "",
        connected_integrations=connected_for_pack,
    )
    if enrich_plan is not None and conversation_id:
        from app.services.conversation_state_service import get_conversation_state_service

        state = get_conversation_state_service(active)
        pending_params = dict(enrich_plan)
        await state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": pending_params,
                "pending_task": {
                    "type": "create_workflow",
                    "status": "awaiting_confirm",
                    "params": pending_params,
                },
                "recent_user_messages": [message or ""],
            },
            client=client,
        )
        refreshed = await state.get_task_state(
            conversation_id, org_id, client=client
        )
        confirm_message = format_pack_common_msp_enrich_confirm_message(enrich_plan)
        result.outcome_kind = "confirmation_request"
        result.tool_name = str(enrich_plan.get("tool_name") or "assistant_create_workflow")
        result.tool_invoke_action = str(
            enrich_plan.get("invoke_action") or "assistant.create_workflow"
        )
        result.tool_arguments = {
            "goal": enrich_plan.get("workflow_goal"),
            "name": enrich_plan.get("workflow_name"),
            "workflow_slug": enrich_plan.get("workflow_slug"),
        }
        result.requires_write_approval = True
        result.live_served = True
        result.model = f"{result.model or 'unified_turn'}+pack_common_msp_enrich"
        result.user_message = confirm_message
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
                confirm_message, context="unified_turn_live_pack_common_msp_enrich"
            ),
            "task_state": refreshed,
            "pending_task": (refreshed or {}).get("pending_task"),
            "workflow_status": "awaiting_confirm",
            "answer_explanation": "Unified turn live (pack-common MSP Clay enrich)",
            "model": result.model or "unified_turn_live",
            "unified_outcome_kind": "confirmation_request",
        }

    from app.services.unified_turn_classical_fallback import (
        should_defer_unified_turn_live_to_classical,
    )
    from app.services.chat_orchestration_service import ChatOrchestrationService

    from app.services.conversational_turn_gate import is_human_moment_venting_no_ask

    human_moment = is_human_moment_venting_no_ask(message or "")

    # F2: structured needs_tool_sse — orch / tool-shaped turns set the flag even
    # when the model returned conversational text (no bare apollo/slack keyword).
    # Skip for rule-10 human-moment vents (no explicit ask).
    if (
        not human_moment
        and not result.needs_tool_sse
        and ChatOrchestrationService.is_orchestration_intent(
            message or "",
            task_state or {},
            list(result.connected_integrations or connected_integrations or []),
        )
    ):
        result.needs_tool_sse = True
    if (
        not human_moment
        and not result.needs_tool_sse
        and isinstance(classification, dict)
        and classification.get("requires_action")
        and result.outcome_kind
        in {"conversational_reply", "clarifying_question", "knowledge_boundary"}
    ):
        # Probe/tool SSE path when classical classifiers already flagged action.
        from app.services.unified_turn_classical_fallback import (
            message_requires_classical_tool_sse,
        )

        if message_requires_classical_tool_sse(message or ""):
            result.needs_tool_sse = True

    if human_moment:
        result.needs_tool_sse = False

    would_defer = should_defer_unified_turn_live_to_classical(
        mode_key=mode_key,
        outcome_kind=str(result.outcome_kind or ""),
        message=message,
        classification=classification,
        needs_tool_sse=bool(result.needs_tool_sse),
    )
    # Class rule: never bare-defer a multi-step orchestration intent. Stage the
    # plan on LIVE first (HubSpot+Slack TRY chip, etc.) — same structural order
    # as pack-common intents. Bare fallthrough lets classical invent wrong steps.
    if would_defer and conversation_id:
        from app.services.chat_orchestration_service import (
            ChatOrchestrationService,
            get_chat_orchestration_service,
        )

        if ChatOrchestrationService.is_orchestration_intent(
            message or "",
            task_state or {},
            connected_for_pack,
        ):
            orch_turn = await get_chat_orchestration_service(active).process_turn(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                message=message or "",
                classification=classification or {},
                task_state=task_state or {},
                connected_integrations=connected_for_pack,
                client=client,
                environment_name=environment_name,
            )
            if orch_turn and orch_turn.get("stop_pipeline"):
                result.live_served = True
                result.outcome_kind = "confirmation_request"
                result.model = (
                    f"{result.model or 'unified_turn'}+live_orchestration_before_defer"
                )
                result.user_message = str(orch_turn.get("message") or "")
                emit_unified_turn_shadow_audit(
                    client=client,
                    org_id=org_id,
                    actor_id=user_id,
                    conversation_id=conversation_id,
                    result=result,
                )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": str(orch_turn.get("dialogue_mode") or "confirm"),
                    "message": finalize_user_facing_message(
                        result.user_message,
                        context="unified_turn_live_orchestration_before_defer",
                    ),
                    "task_state": orch_turn.get("task_state"),
                    "pending_task": orch_turn.get("pending_task"),
                    "workflow_status": orch_turn.get("workflow_status"),
                    "answer_explanation": str(
                        orch_turn.get("answer_explanation")
                        or "Unified turn live (orchestration before defer)"
                    ),
                    "model": result.model or "unified_turn_live",
                    "unified_outcome_kind": "confirmation_request",
                    "execution_result": orch_turn.get("execution_result"),
                }

    if would_defer:
        defer_reason = (
            "defer_connector_tool_proposal"
            if str(result.outcome_kind or "") == "connector_tool_proposal"
            else "defer_classical_tool_sse"
        )
        _mark_live_fallthrough(result, defer_reason)
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
        if unified_live_message_violates_no_pending_hold(
            message=result.user_message, task_state=task_state
        ):
            _mark_live_fallthrough(result, "violates_no_pending_hold")
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=result,
            )
            return None
        from app.services.unified_turn_connector_grounding import (
            unified_live_message_claims_false_disconnect,
        )

        if not result.connected_integrations:
            result.connected_integrations = [
                str(c).strip().lower()
                for c in (connected_integrations or [])
                if str(c).strip()
            ]
        if unified_live_message_claims_false_disconnect(
            result.user_message,
            result.connected_integrations,
        ):
            _mark_live_fallthrough(result, "false_connector_disconnect_claim")
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=result,
            )
            return None
        result.user_message = await _maybe_prepend_mixed_social_ack(
            message=message,
            body=result.user_message,
            task_state=task_state,
            org_id=org_id,
            settings=active,
        )
        result.live_served = True
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return _unified_live_turn_payload(result, task_state)

    if result.outcome_kind == "connector_tool_proposal" and result.tool_name:
        from app.services.pending_reply_classifier import (
            build_pending_snapshot,
            format_unrelated_hold_prompt,
            has_pending_family,
        )

        if has_pending_family(task_state):
            snap = build_pending_snapshot(task_state)
            pending_action = str(snap.invoke_action or "").strip().lower()
            proposed = str(result.tool_name or "").replace("_", ".").lower()
            # Staging a different write while something is pending must ask hold/abandon first.
            if pending_action and proposed and pending_action not in proposed and proposed not in pending_action:
                hold = UnifiedTurnShadowResult(
                    outcome_kind="clarifying_question",
                    user_message=format_unrelated_hold_prompt(snap, new_request=message),
                    live_served=True,
                    model="pending_reply_classifier",
                )
                emit_unified_turn_shadow_audit(
                    client=client,
                    org_id=org_id,
                    actor_id=user_id,
                    conversation_id=conversation_id,
                    result=hold,
                )
                return _unified_live_turn_payload(hold, task_state)
        from app.services.react_write_gate import plan_from_react_tool_call
        from app.services.tool_registry import get_tool_registry

        registry = get_tool_registry()
        from app.services.chat_write_intent import evaluate_connector_tool_proposal

        review = evaluate_connector_tool_proposal(
            message=message or "",
            tool_name=str(result.tool_name or ""),
            invoke_action=result.tool_invoke_action,
            args=dict(result.tool_arguments or {}),
        )
        if review.action == "clarify":
            clarify = UnifiedTurnShadowResult(
                outcome_kind="clarifying_question",
                user_message=review.clarify_message,
                live_served=True,
                model=result.model or "connector_write_intent",
                connected_integrations=list(result.connected_integrations or []),
            )
            emit_unified_turn_shadow_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                result=clarify,
            )
            return _unified_live_turn_payload(clarify, task_state)

        plan = plan_from_react_tool_call(
            review.tool_name or result.tool_name,
            review.tool_arguments or result.tool_arguments,
            registry,
            requires_approval=bool(result.requires_write_approval),
        )
        if plan is None or not conversation_id:
            _mark_live_fallthrough(result, "write_plan_unavailable")
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
            from app.services.connector_action_workflows import (
                format_write_approval_message,
                missing_params_stage_patch,
                scrub_gmail_write_plan,
            )
            from app.services.connector_parameter_inference import (
                ParameterInferenceContext,
                infer_missing_parameters,
            )
            from app.services.connector_session_state import load_connector_session
            from app.services.conversation_state_service import get_conversation_state_service
            from app.services.pack_common_intent_defaults import apply_pack_common_defaults

            plan = enrich_plan_inference_metadata(plan, message=message or "")
            plan = apply_pack_common_defaults(plan, message=message or "")
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
            plan = scrub_gmail_write_plan(plan)
            state = get_conversation_state_service(active)
            from app.services.parameter_ledger import (
                get_ledger,
                ledger_patch,
                seal_unified_turn_plan_args,
            )

            # Seal LIVE-extracted args so pending/retry cannot re-regex-overwrite them.
            sealed_ledger = seal_unified_turn_plan_args(
                plan, ledger=get_ledger(task_state or {})
            )
            task_state = {**(task_state or {}), **ledger_patch(sealed_ledger)}
            # Dual-path SoT with classical chat: never ask for yes until required args exist.
            staged_missing = missing_params_stage_patch(
                plan,
                message or "",
                task_state=task_state or {},
                seal_source="unified_turn_live",
            )
            if staged_missing:
                clarification, stage_patch = staged_missing
                await state.update_task_state(
                    conversation_id,
                    org_id,
                    {
                        **ledger_patch(sealed_ledger),
                        **stage_patch,
                        "recent_user_messages": [message or ""],
                    },
                    client=client,
                )
                refreshed = await state.get_task_state(
                    conversation_id, org_id, client=client
                )
                clarify_message = clarification.message
                if result.user_message:
                    from app.services.user_facing_copy_guard import dedupe_repeated_paragraphs

                    preamble = dedupe_repeated_paragraphs(result.user_message.strip())
                    body = (clarify_message or "").strip()
                    if body and body not in preamble:
                        clarify_message = f"{preamble}\n\n{body}"
                    elif preamble:
                        clarify_message = preamble
                clarify_message = await _maybe_prepend_mixed_social_ack(
                    message=message,
                    body=clarify_message,
                    task_state=task_state,
                    org_id=org_id,
                    settings=active,
                )
                result.live_served = True
                result.outcome_kind = "clarifying_question"
                emit_unified_turn_shadow_audit(
                    client=client,
                    org_id=org_id,
                    actor_id=user_id,
                    conversation_id=conversation_id,
                    result=result,
                )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": clarification.dialogue_mode or "clarify",
                    "message": finalize_user_facing_message(
                        clarify_message, context="unified_turn_live_awaiting_params"
                    ),
                    "task_state": refreshed,
                    "pending_task": (refreshed or {}).get("pending_task"),
                    "workflow_status": clarification.status,
                    "answer_explanation": "Unified turn live (awaiting params)",
                    "model": result.model or "unified_turn_live",
                    "unified_outcome_kind": "clarifying_question",
                }

            pending_params = {
                **ChatConnectorExecutionService.plan_to_dict(plan),
                "status": "awaiting_confirm",
                "source": "unified_turn_live",
            }
            await state.update_task_state(
                conversation_id,
                org_id,
                {
                    **ledger_patch(sealed_ledger),
                    "pending_task": {
                        "type": "connector_action",
                        "status": "awaiting_confirm",
                        "params": pending_params,
                    },
                    "recent_user_messages": [message or ""],
                },
                client=client,
            )
            refreshed = await state.get_task_state(conversation_id, org_id, client=client)
            confirm_message = format_write_approval_message(plan)
            if result.user_message:
                from app.services.user_facing_copy_guard import dedupe_repeated_paragraphs

                preamble = dedupe_repeated_paragraphs(result.user_message.strip())
                approval = confirm_message.strip()
                if approval and approval not in preamble:
                    confirm_message = f"{preamble}\n\n{approval}"
                elif preamble:
                    confirm_message = preamble
            confirm_message = await _maybe_prepend_mixed_social_ack(
                message=message,
                body=confirm_message,
                task_state=task_state,
                org_id=org_id,
                settings=active,
            )
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
        _mark_live_fallthrough(result, "read_tool_classical")
        emit_unified_turn_shadow_audit(
            client=client,
            org_id=org_id,
            actor_id=user_id,
            conversation_id=conversation_id,
            result=result,
        )
        return None

    _mark_live_fallthrough(result, f"unhandled_kind_{result.outcome_kind}")
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
