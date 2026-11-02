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
    task_state: dict[str, Any] | None = None,
    conversation_history: list[Any] | None = None,
    spoken_mode: bool = False,
) -> Any:
    """Run shared intelligence and RETRIEVE→GOVERN; execution gates remain downstream.

    Missing/foreign tenant identity is an error, not degraded intelligence.
    """
    if not org_id or (agent and agent.get("org_id") is not None and agent["org_id"] != org_id):
        raise ValueError("A matching execution organization is required")
    try:
        from app.services.cognitive_turn_kernel import (
            CognitiveTurnRequest,
            get_cognitive_turn_kernel,
        )

        from app.services.execution_intelligence_context import collect_execution_intelligence

        active = settings or get_settings()
        intelligence = await collect_execution_intelligence(
            settings=active, org_id=org_id, task=message or "", agent=agent or {}, briefing=parameters or {},
        ) if getattr(active, "cognitive_turn_kernel_enabled", True) else {}
        return await get_cognitive_turn_kernel(active).run_pre_act(
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
                task_state=task_state,
                conversation_history=conversation_history,
                intelligence_pack=intelligence,
                spoken_mode=spoken_mode,
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
    agent = kwargs.get("agent") or {}
    if not kwargs.get("org_id") or (agent.get("org_id") is not None and agent["org_id"] != kwargs["org_id"]):
        raise ValueError("A matching execution organization is required")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_kernel_for_entry(**kwargs))

    import concurrent.futures
    import contextvars

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            inherited = contextvars.copy_context()
            return pool.submit(inherited.run, lambda: asyncio.run(run_kernel_for_entry(**kwargs))).result(
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
        bag["cognitiveDialogueSection"] = sections.get("dialogue_section") or ""
        bag["cognitiveSessionContinuitySection"] = sections.get("session_continuity_section") or ""
        bag["cognitiveIntelligenceSection"] = sections.get("intelligence_section") or ""
        from app.services.execution_intelligence_context import capability_diagnostics

        bag["cognitiveIntelligenceStatus"] = capability_diagnostics(getattr(ctx, "intelligence_pack", {}))
        bag["cognitiveOutcomeBiasSection"] = sections.get("outcome_bias_section") or ""
        bag["cognitiveStages"] = [
            getattr(s, "stage", s) for s in (getattr(ctx, "stages", None) or [])
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_evidence_attach_failed error=%s", exc)
    return bag
