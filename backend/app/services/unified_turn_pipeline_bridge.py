"""Bridge unified-turn latency_breakdown into ai_pipeline_latency for Performance tab."""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Ordered stages for Performance waterfall (TTFT path).
UNIFIED_TURN_PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("registry_tools_ms", "unified_registry_tools"),
    ("narrow_tools_ms", "unified_narrow_tools"),
    ("embed_query_ms", "unified_embed_query"),
    ("context_prompt_ms", "unified_context_prompt"),
    ("openai_create_schedule_ms", "unified_openai_schedule"),
    ("model_ttft_ms", "unified_model_ttft"),
    ("pre_first_token_overhead_ms", "unified_pre_token_overhead"),
    ("model_total_ms", "unified_model_total"),
)

CLASSICAL_PIPELINE_STAGES: tuple[str, ...] = (
    "retrieval",
    "rerank",
    "validation",
    "generation",
    "graph_lookup",
)


def bridge_unified_turn_breakdown_to_pipeline(
    settings: Any,
    *,
    org_id: str,
    breakdown: dict[str, Any],
    message_id: str | None = None,
    model_used: str | None = None,
    client: Any | None = None,
) -> None:
    """Fire-and-forget pipeline latency rows from unified-turn breakdown."""
    if not org_id or not breakdown:
        return

    from app.services.latency_tracking import log_pipeline_latency

    async def _emit() -> None:
        for bd_key, stage_name in UNIFIED_TURN_PIPELINE_STAGES:
            raw = breakdown.get(bd_key)
            if not isinstance(raw, (int, float)) or raw < 0:
                continue
            try:
                await log_pipeline_latency(
                    settings,
                    org_id=org_id,
                    stage_name=stage_name,
                    duration_ms=int(raw),
                    message_id=message_id,
                    model_used=model_used,
                    client=client,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "unified_turn_pipeline_bridge_failed stage=%s error=%s",
                    stage_name,
                    exc,
                )

        wall = breakdown.get("wall_to_first_token_ms")
        if isinstance(wall, (int, float)) and wall >= 0:
            try:
                await log_pipeline_latency(
                    settings,
                    org_id=org_id,
                    stage_name="unified_wall_ttft",
                    duration_ms=int(wall),
                    message_id=message_id,
                    model_used=model_used,
                    client=client,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("unified_turn_pipeline_bridge_wall_failed error=%s", exc)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_emit())
    except RuntimeError:
        asyncio.run(_emit())
