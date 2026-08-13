"""CognitivePlanner — unified plan producer for CognitiveTurnKernel PLAN stage."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class CognitivePlanner:
    """
    Produce a ``current_plan``-compatible dict for task_state.

    Prefer an existing ``task_state.current_plan`` when present; otherwise emit a
    lightweight heuristic plan from the user message and memory/knowledge packs.
    """

    def plan(
        self,
        message: str,
        task_state: dict[str, Any] | None,
        memory_pack: dict[str, Any] | None,
        knowledge_pack: dict[str, Any] | None,
    ) -> dict[str, Any]:
        state = task_state if isinstance(task_state, dict) else {}
        existing = state.get("current_plan")
        if isinstance(existing, dict) and (existing.get("steps") is not None or existing.get("summary")):
            plan = dict(existing)
            plan.setdefault("source", plan.get("source") or "task_state")
            plan.setdefault("steps", list(plan.get("steps") or []))
            plan.setdefault("summary", str(plan.get("summary") or ""))
            return plan

        text = (message or "").strip()
        summary = text[:240] if text else "No user message provided"
        steps: list[dict[str, Any]] = []
        if text:
            steps.append(
                {
                    "step_id": "understand",
                    "title": "Understand request",
                    "description": summary,
                    "status": "pending",
                }
            )
            mem_hits = _pack_hit_count(memory_pack)
            know_hits = _pack_hit_count(knowledge_pack)
            if mem_hits or know_hits:
                steps.append(
                    {
                        "step_id": "apply_context",
                        "title": "Apply recalled context",
                        "description": (
                            f"Use memory ({mem_hits} items) and knowledge "
                            f"({know_hits} items) when answering or acting."
                        ),
                        "status": "pending",
                    }
                )
            steps.append(
                {
                    "step_id": "respond_or_act",
                    "title": "Respond or propose action",
                    "description": "Produce the user-facing reply or governed write proposal.",
                    "status": "pending",
                }
            )

        return {
            "steps": steps,
            "summary": summary,
            "source": "cognitive_planner",
        }


def _pack_hit_count(pack: dict[str, Any] | None) -> int:
    if not isinstance(pack, dict):
        return 0
    total = 0
    for key, value in pack.items():
        if key in {"prompt_section", "summary"}:
            continue
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, str) and value.strip():
            total += 1
    return total
