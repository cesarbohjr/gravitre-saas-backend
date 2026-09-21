"""2.0-I typed vs spoken semantic snapshot — STT output is text; kernel must match."""
from __future__ import annotations

from typing import Any

from app.services.canonical_cognitive_resolution import should_skip_unified_live_for_compiled_read
from app.services.multi_source_diagnostic import match_diagnostic_recipe
from app.services.task_continuity import decide_task_continuity


def semantic_kernel_snapshot(
    message: str,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
) -> dict[str, Any]:
    """Comparable canonical state for a typed line and an equivalent STT transcript."""
    state = task_state if isinstance(task_state, dict) else {}
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    pending = state.get("pending_action") if isinstance(state.get("pending_action"), dict) else {}
    return {
        "continuity": decide_task_continuity(message, state),
        "skip_unified_live": should_skip_unified_live_for_compiled_read(
            message, state, connected_integrations
        ),
        "diagnostic_recipe": match_diagnostic_recipe(message),
        "capability_id": plan.get("capability_id"),
        "plan_id": plan.get("plan_id"),
        "pending_action": pending.get("action"),
        "approval_state": pending.get("status"),
        "write_allowed": pending.get("write_allowed"),
    }


def typed_matches_spoken(
    typed: str,
    spoken_transcript: str,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
) -> bool:
    return semantic_kernel_snapshot(typed, task_state, connected_integrations) == semantic_kernel_snapshot(
        spoken_transcript, task_state, connected_integrations
    )
