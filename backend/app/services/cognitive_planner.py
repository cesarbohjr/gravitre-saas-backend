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
            plan.setdefault("plan_kind", "strategic_reasoning")
            plan.setdefault("executable", False)
            raw_exec = state.get("execution_plan")
            if isinstance(raw_exec, dict) and raw_exec.get("plan_id"):
                plan.setdefault("execution_plan_id", raw_exec.get("plan_id"))
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

        exec_plan_id = None
        raw_exec = state.get("execution_plan")
        if isinstance(raw_exec, dict):
            exec_plan_id = raw_exec.get("plan_id")
        plan = {
            "steps": steps,
            "summary": summary,
            "source": "cognitive_planner",
            "plan_kind": "strategic_reasoning",
            "executable": False,
            "execution_plan_id": exec_plan_id,
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

        # Outcome Ownership compound-objective composition. Runtime callers may
        # attach normalized resource descriptors to task_state; the planner
        # composes them by capability instead of forcing the user to name tools.
        objective = state.get("objective_contract") if isinstance(state.get("objective_contract"), dict) else {}
        required = {
            str(x).strip()
            for x in (objective.get("required_capabilities") or [])
            if str(x).strip()
        }
        raw_resources = state.get("capability_resources")
        if required and isinstance(raw_resources, list):
            try:
                from app.services.objective_capability_composer import (
                    CapabilityResource,
                    compose_capability_resources,
                )

                resources = []
                for raw in raw_resources:
                    if not isinstance(raw, dict):
                        continue
                    resources.append(
                        CapabilityResource(
                            resource_id=str(raw.get("resource_id") or raw.get("id") or ""),
                            kind=str(raw.get("kind") or ""),
                            capabilities=frozenset(
                                str(x).strip()
                                for x in (raw.get("capabilities") or [])
                                if str(x).strip()
                            ),
                            connected=raw.get("connected") is True,
                            writable=bool(raw.get("writable", False)),
                            verified=bool(raw.get("verified", False)),
                            priority=int(raw.get("priority") or 100),
                        )
                    )
                composition = compose_capability_resources(
                    required_capabilities=required,
                    resources=[r for r in resources if r.resource_id],
                    require_write=bool(objective.get("requires_write", False)),
                    write_capabilities={
                        str(x).strip()
                        for x in (objective.get("write_capabilities") or [])
                        if str(x).strip()
                    },
                )
                enriched = dict(enriched)
                enriched["capability_composition"] = composition
                enriched["objective_contract"] = {
                    "objective": objective.get("objective") or summary,
                    "required_capabilities": sorted(required),
                    "requires_write": bool(objective.get("requires_write", False)),
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug("objective_capability_composition_skipped error=%s", exc)
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
