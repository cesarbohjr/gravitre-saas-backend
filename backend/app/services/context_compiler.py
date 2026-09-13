"""Phase B — single ranked context assembly path (orchestrator + kernel merge)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

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
