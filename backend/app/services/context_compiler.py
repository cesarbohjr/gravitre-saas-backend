"""Phase B/E4 — canonical reasoning context assembly (classical + unified LIVE)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

PrepareTurnFn = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class CompiledTurnContextMeta:
    intent_class: str | None
    capability_id: str | None
    kernel_merged: bool
    source: str


def merge_kernel_sections(turn_ctx: Any, cognitive_ctx: Any) -> bool:
    """Merge CognitiveTurnKernel RECALL/KNOWLEDGE into orchestrator turn context."""
    if cognitive_ctx is None or turn_ctx is None:
        return False
    try:
        from app.services.cognitive_turn_kernel import to_prompt_sections

        sections = to_prompt_sections(cognitive_ctx)
        if sections.get("memory_section") and hasattr(turn_ctx, "retrieval"):
            prior = getattr(turn_ctx.retrieval, "memory_section", "") or ""
            turn_ctx.retrieval.memory_section = "\n\n".join(
                p for p in (prior, sections["memory_section"]) if p
            ).strip()
        if sections.get("knowledge_section"):
            prior_k = getattr(turn_ctx, "entity_relationship_section", None) or ""
            if hasattr(turn_ctx, "entity_relationship_section"):
                turn_ctx.entity_relationship_section = "\n\n".join(
                    p for p in (prior_k, sections["knowledge_section"]) if p
                ).strip()
        bias = (sections.get("outcome_bias_section") or "").strip()
        if bias and hasattr(turn_ctx, "retrieval"):
            prior_m = getattr(turn_ctx.retrieval, "memory_section", "") or ""
            turn_ctx.retrieval.memory_section = "\n\n".join(
                p for p in (prior_m, bias) if p
            ).strip()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("context_compiler_kernel_merge_skipped error=%s", exc)
        return False


async def compile_assistant_turn_context(
    *,
    classification: dict[str, Any],
    task_state: dict[str, Any] | None,
    prepare_turn: PrepareTurnFn,
    cognitive_ctx: Any = None,
    prefetched_turn_ctx: Any = None,
) -> tuple[Any, CompiledTurnContextMeta]:
    """Run orchestrator context assembly once; merge kernel sections when present."""
    intent_class = None
    needs = (task_state or {}).get("cognitive_resolution_needs")
    if isinstance(needs, dict):
        reason = str(needs.get("reason") or "").strip()
        if reason:
            intent_class = reason

    capability_id = str(classification.get("capability_id") or "").strip() or None
    enriched = dict(classification)
    if intent_class and not enriched.get("intent_class"):
        enriched["intent_class"] = intent_class

    if prefetched_turn_ctx is not None:
        turn_ctx = prefetched_turn_ctx
        source = "prefetch"
    else:
        turn_ctx = await prepare_turn(enriched)
        source = "inline"

    kernel_merged = merge_kernel_sections(turn_ctx, cognitive_ctx)
    meta = CompiledTurnContextMeta(
        intent_class=intent_class,
        capability_id=capability_id,
        kernel_merged=kernel_merged,
        source=source,
    )
    return turn_ctx, meta


ContextInclusionAction = Literal["INCLUDE", "EXCLUDE", "RETRIEVE", "SUMMARIZE", "DEFER"]


@dataclass(frozen=True)
class InclusionDecision:
    source: str
    action: ContextInclusionAction
    reason: str


@dataclass(frozen=True)
class CompiledTurnContext:
    """Canonical reasoning context for foundation-model calls (E4)."""

    user_parts: tuple[tuple[str, str], ...]
    knowledge_meta: dict[str, Any] | None
    registry_plan: Any
    inclusion_decisions: tuple[InclusionDecision, ...]
    compile_duration_ms: float
    token_estimate: int
    turn_id: str | None = None
    context_compiler_invoked: bool = True
    context_compile_skipped_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def user_content(self) -> str:
        return "\n\n".join(text for _, text in self.user_parts if text)

    def context_parts(self) -> list[tuple[str, str]]:
        return list(self.user_parts)

    def to_trace_dict(self) -> dict[str, Any]:
        included = [d.source for d in self.inclusion_decisions if d.action in {"INCLUDE", "RETRIEVE"}]
        excluded = [d.source for d in self.inclusion_decisions if d.action == "EXCLUDE"]
        deferred = [d.source for d in self.inclusion_decisions if d.action == "DEFER"]
        return {
            "context_compiler_invoked": self.context_compiler_invoked,
            "context_compile_skipped_reason": self.context_compile_skipped_reason,
            "context_sources_considered": [d.source for d in self.inclusion_decisions],
            "context_sources_included": included,
            "context_sources_excluded": excluded,
            "context_sources_deferred": deferred,
            "retrievals_performed": [
                d.source for d in self.inclusion_decisions if d.action == "RETRIEVE"
            ],
            "token_estimate": self.token_estimate,
            "compile_duration_ms": round(self.compile_duration_ms, 2),
            "registry_plan": (
                self.registry_plan.to_explanation_dict()
                if hasattr(self.registry_plan, "to_explanation_dict")
                else {}
            ),
        }


def _estimate_tokens(text: str) -> int:
    return max(0, len(text or "") // 4)


async def compile_unified_reasoning_context(
    *,
    org_id: str,
    user_id: str,
    conversation_id: str | None,
    message: str,
    task_state: dict[str, Any] | None,
    conversation_history: list[dict[str, Any]] | None,
    connected_integrations: list[str] | None,
    client: Any = None,
    settings: Any = None,
    classification: dict[str, Any] | None = None,
    cognitive_context: Any = None,
    research_scope: str | None = None,
    reasoning_depth: str = "full",
    routing_tier: str | None = None,
    mode: str | None = None,
    agent: dict[str, Any] | None = None,
    surface: str | None = None,
) -> CompiledTurnContext:
    """Assemble unified-LIVE reasoning context through one canonical contract (E4).

    Tool schemas and execution availability are intentionally excluded — those
    remain runtime inputs on the unified turn path (ToolRouter / progressive disclosure).
    """
    from app.config import get_settings
    from app.services.context_registry import plan_context_registry

    t0 = time.perf_counter()
    active = settings or get_settings()
    cls = dict(classification or {})
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    if "platform" not in connected:
        connected.append("platform")

    knowledge_assignments: list[dict[str, Any]] = []
    agent_id = str((agent or {}).get("id") or "")
    if agent_id and agent_id not in {"assistant"} and client is not None and org_id:
        try:
            from app.services.agent_knowledge_assignment_service import AgentKnowledgeAssignmentService

            knowledge_assignments = AgentKnowledgeAssignmentService(active).list_assignments(
                client, org_id, agent_id
            )
        except Exception:  # noqa: BLE001
            knowledge_assignments = AgentKnowledgeAssignmentService(active).resolve_assignments(
                agent or {}
            )

    registry_plan = plan_context_registry(
        query=message or "",
        classification=cls,
        connected_integrations=connected,
        task_state=task_state,
        routing_tier=routing_tier,
        mode=mode,
        knowledge_assignments=knowledge_assignments,
    )

    from app.services.unified_turn_reasoning_service import (
        _is_remind_me_turn,
        _last_assistant_snippet,
        _prior_recommendations_block,
        _standing_user_corrections_block,
    )
    from app.services.unified_turn_pending_context import build_unified_turn_pending_context

    decisions: list[InclusionDecision] = []
    parts: list[tuple[str, str]] = []

    def _record(source: str, action: ContextInclusionAction, reason: str) -> None:
        decisions.append(InclusionDecision(source=source, action=action, reason=reason))

    def _add_part(label: str, text: str) -> None:
        parts.append((label, text))

    remind_me = _is_remind_me_turn(message)

    pending_block = build_unified_turn_pending_context(
        task_state,
        last_assistant_message=_last_assistant_snippet(conversation_history),
    )
    if pending_block:
        _add_part("pending_state", pending_block)
        _record("pending_action", "INCLUDE", "conversation_state")
    else:
        _add_part(
            "pending_state",
            "NO PENDING STATE this turn. Do not mention abandon/hold or a pending item.",
        )
        _record("pending_action", "EXCLUDE", "no_pending_state")

    if registry_plan.slice_enabled("connector"):
        from app.services.conversational_reply_service import build_capability_snapshot

        capability_block = build_capability_snapshot(
            connected_integrations=connected,
            client=client,
            org_id=org_id,
        )
        _add_part(
            "connected_integrations",
            "CONNECTED INTEGRATIONS THIS ORG (authoritative executable list for this turn — "
            "vendors listed here ARE connected; vendors absent are NOT connected for this org; "
            "absence is not uncertainty; answer connection questions directly from this list "
            "or from connector status data already loaded — never tell the user internal tool "
            "names or that you lack data when absence means not connected):\n"
            + capability_block,
        )
        _record("connector_context", "INCLUDE", "registry:connector")
    else:
        _record("connector_context", "EXCLUDE", "registry:connector_off")

    from app.services.chat_write_intent import build_gmail_write_intent_prompt_section

    intent_hint = build_gmail_write_intent_prompt_section(message or "")
    if intent_hint:
        _add_part("write_intent_hint", intent_hint)
        _record("write_intent", "INCLUDE", "gmail_write_shape")
    else:
        _record("write_intent", "EXCLUDE", "not_write_shaped")

    standing = _standing_user_corrections_block(conversation_history)
    if standing:
        _add_part("standing_corrections", standing)
        _record("standing_corrections", "INCLUDE", "user_corrections_in_thread")
    else:
        _record("standing_corrections", "EXCLUDE", "none")

    prior_recs = _prior_recommendations_block(conversation_history) if remind_me else ""
    if prior_recs:
        _add_part("prior_recommendations", prior_recs)
        _record("prior_recommendations", "INCLUDE", "remind_me_turn")
    else:
        _record("prior_recommendations", "EXCLUDE", "not_remind_me")

    cognitive_prompt_sections: dict[str, str] = {}
    if cognitive_context is not None and not remind_me:
        try:
            from app.services.cognitive_turn_kernel import to_prompt_sections

            cognitive_prompt_sections = to_prompt_sections(cognitive_context)
            _record("cognitive_kernel", "INCLUDE", "kernel_sections_available")
        except Exception as exc:  # noqa: BLE001
            logger.warning("context_compiler_kernel_sections_unavailable error=%s", exc)
            _record("cognitive_kernel", "DEFER", "kernel_sections_failed")
    elif remind_me:
        _record("cognitive_kernel", "EXCLUDE", "remind_me_turn")
    else:
        _record("cognitive_kernel", "EXCLUDE", "no_cognitive_context")

    knowledge_meta: dict[str, Any] | None = None
    rag_enabled = registry_plan.slice_enabled("rag") or registry_plan.slice_enabled("pack_state")
    if remind_me:
        knowledge_meta = {"skipped": "remind_me_turn"}
        _record("knowledge_fabric", "EXCLUDE", "remind_me_turn")
    elif client is not None and org_id and rag_enabled:
        from app.services.unified_turn_knowledge_context import build_unified_turn_knowledge_context

        _record("knowledge_fabric", "RETRIEVE", "registry:rag_or_pack")
        knowledge_block, knowledge_meta = await build_unified_turn_knowledge_context(
            org_id=org_id,
            query=message or "",
            client=client,
            settings=active,
            classification=cls,
            agent=agent,
            knowledge_assignments=knowledge_assignments,
            connected_integrations=connected,
            supplemental_context=cognitive_prompt_sections,
            research_scope=research_scope,
            reasoning_depth=reasoning_depth,
            actor_id=user_id,
            conversation_id=conversation_id,
        )
        if knowledge_block:
            _add_part("knowledge_fabric", knowledge_block)
        else:
            _record("knowledge_fabric", "EXCLUDE", "retrieval_empty")
    else:
        reason = "registry:rag_off" if not rag_enabled else "missing_client_or_org"
        knowledge_meta = {"skipped": reason}
        _record("knowledge_fabric", "EXCLUDE", reason)

    if cognitive_context is not None and not remind_me:
        try:
            from app.services.cognitive_turn_kernel import memory_recall_signal

            mem = (cognitive_prompt_sections.get("memory_section") or "").strip()
            know = (cognitive_prompt_sections.get("knowledge_section") or "").strip()
            bias = (cognitive_prompt_sections.get("outcome_bias_section") or "").strip()
            ranking_meta = (
                (knowledge_meta or {}).get("contextRanking")
                if isinstance(knowledge_meta, dict)
                else None
            )
            managed_supplemental = bool(
                isinstance(ranking_meta, dict)
                and ranking_meta.get("mode") == "active"
                and ranking_meta.get("managedSupplementalSections")
            )
            if managed_supplemental:
                _record("kernel_memory", "DEFER", "knowledge_fabric_managed_supplemental")
                _record("kernel_knowledge", "DEFER", "knowledge_fabric_managed_supplemental")
                _record("outcome_bias", "DEFER", "knowledge_fabric_managed_supplemental")
            else:
                if mem and registry_plan.slice_enabled("user"):
                    _add_part("memory_recall", mem)
                    _record("kernel_memory", "INCLUDE", "recall_section")
                else:
                    _record("kernel_memory", "EXCLUDE", "empty_or_user_slice_off")
                if know and (registry_plan.slice_enabled("rag") or registry_plan.slice_enabled("graph")):
                    _add_part("kernel_knowledge_section", know)
                    _record("kernel_knowledge", "INCLUDE", "knowledge_section")
                else:
                    _record("kernel_knowledge", "EXCLUDE", "empty_or_slice_off")
                if bias:
                    _add_part("outcome_bias", bias)
                    _record("outcome_bias", "INCLUDE", "outcome_bias_section")
                else:
                    _record("outcome_bias", "EXCLUDE", "empty")
            kernel_meta = {
                "cognitiveTurnId": getattr(cognitive_context, "turn_id", None),
                "outcomeBiasInjected": bool(bias),
                "memoryRecall": memory_recall_signal(cognitive_context),
            }
            if isinstance(knowledge_meta, dict):
                knowledge_meta = {**knowledge_meta, **kernel_meta}
            else:
                knowledge_meta = kernel_meta
        except Exception as exc:  # noqa: BLE001
            logger.warning("context_compiler_kernel_section_merge_failed error=%s", exc)

    if surface == "intelligence_hub":
        _record("surface_context", "INCLUDE", "intelligence_hub_surface")
    else:
        _record("surface_context", "EXCLUDE", f"surface:{surface or 'assistant'}")

    _add_part("user_message", f"USER MESSAGE:\n{(message or '').strip()}")
    _record("user_message", "INCLUDE", "required")

    user_content = "\n\n".join(text for _, text in parts)
    compile_ms = (time.perf_counter() - t0) * 1000.0
    turn_id = getattr(cognitive_context, "turn_id", None) if cognitive_context is not None else None

    return CompiledTurnContext(
        turn_id=str(turn_id) if turn_id else None,
        user_parts=tuple(parts),
        knowledge_meta=knowledge_meta if isinstance(knowledge_meta, dict) else None,
        registry_plan=registry_plan,
        inclusion_decisions=tuple(decisions),
        compile_duration_ms=compile_ms,
        token_estimate=_estimate_tokens(user_content),
        metadata={"surface": surface or "assistant"},
    )
