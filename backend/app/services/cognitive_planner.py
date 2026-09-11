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
        *,
        connected_integrations: list[str] | None = None,
        department: str | None = None,
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
            scoring = (knowledge_pack or {}).get("signal_scoring") if isinstance(knowledge_pack, dict) else None
            if isinstance(scoring, dict):
                priorities = list(scoring.get("priorities") or [])
                gaps = list(scoring.get("gaps") or [])
                if priorities:
                    top = priorities[0]
                    steps.insert(
                        1,
                        {
                            "step_id": "prioritize_scored_intelligence",
                            "title": "Prioritize from scored intelligence",
                            "description": (
                                f"{top.get('title') or 'Top scored item'} — "
                                f"score {top.get('priorityScore')}/100 "
                                f"({top.get('priorityBand') or 'unbanded'}). "
                                "Contributions are source-cited, not an opaque rank."
                            ),
                            "status": "pending",
                        },
                    )
                elif gaps:
                    steps.insert(
                        1,
                        {
                            "step_id": "prioritize_scored_intelligence",
                            "title": "Prioritize from scored intelligence",
                            "description": (
                                "No scored rows yet: "
                                + "; ".join(str(g) for g in gaps[:2])
                            ),
                            "status": "pending",
                        },
                    )

        plan = {
            "steps": steps,
            "summary": summary,
            "source": "cognitive_planner",
        }
        scoring = (knowledge_pack or {}).get("signal_scoring") if isinstance(knowledge_pack, dict) else None
        if isinstance(scoring, dict):
            plan["signal_scoring"] = {
                "department": scoring.get("department"),
                "priority_count": len(scoring.get("priorities") or []),
                "gaps": list(scoring.get("gaps") or [])[:4],
                "explainable": True,
            }
        from app.capability_ontology.cognitive_recipe_planner import enrich_plan_with_recipe

        enriched = enrich_plan_with_recipe(
            plan,
            query=text,
            connected_integrations=connected_integrations,
            department=department,
        )
        if isinstance(enriched, dict) and "signal_scoring" in plan:
            enriched["signal_scoring"] = plan["signal_scoring"]
        return enriched


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
