"""Entry adapters that force CognitiveTurnKernel intake for non-chat surfaces."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_kernel_for_entry(
    *,
    org_id: str,
    message: str,
    surface: str,
    entry_point: str,
    intent: str,
    user_id: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    client: Any = None,
    settings: Settings | None = None,
    agent: dict[str, Any] | None = None,
) -> Any:
    """Run RETRIEVE→GOVERN for an entry adapter. Never raises."""
    try:
        from app.services.cognitive_turn_kernel import (
            CognitiveTurnRequest,
            get_cognitive_turn_kernel,
        )

        return await get_cognitive_turn_kernel(settings or get_settings()).run_pre_act(
            CognitiveTurnRequest(
                org_id=org_id,
                user_id=user_id,
                agent_id=agent_id,
                conversation_id=conversation_id,
                message=message or "",
                surface=surface,
                entry_point=entry_point,
                intent=intent,
                parameters=parameters or {},
                client=client,
                agent=agent,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cognitive_entry_adapter_failed surface=%s entry=%s error=%s",
            surface,
            entry_point,
            exc,
        )
        return None


def run_kernel_for_entry_sync(**kwargs: Any) -> Any:
    """Sync wrapper for sync extension/confirm paths.

    When already inside a running event loop (async FastAPI handlers calling sync
    bridge helpers), run the coroutine on a short-lived worker thread so callers
    still receive the CognitiveTurnContext instead of fire-and-forget None.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_kernel_for_entry(**kwargs))

    import concurrent.futures

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(run_kernel_for_entry(**kwargs))).result(
                timeout=60
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_entry_adapter_sync_thread_failed error=%s", exc)
        return None


def attach_kernel_pack_to_evidence(evidence: dict[str, Any] | None, ctx: Any) -> dict[str, Any]:
    """Merge kernel memory/knowledge into a council evidence bag."""
    bag = dict(evidence or {})
    if ctx is None:
        return bag
    try:
        from app.services.cognitive_turn_kernel import to_prompt_sections

        sections = to_prompt_sections(ctx)
        bag["cognitiveTurnId"] = getattr(ctx, "turn_id", None)
        bag["cognitiveMemorySection"] = sections.get("memory_section") or ""
        bag["cognitiveKnowledgeSection"] = sections.get("knowledge_section") or ""
        bag["cognitiveOutcomeBiasSection"] = sections.get("outcome_bias_section") or ""
        bag["cognitiveStages"] = [
            getattr(s, "stage", s) for s in (getattr(ctx, "stages", None) or [])
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_evidence_attach_failed error=%s", exc)
    return bag
