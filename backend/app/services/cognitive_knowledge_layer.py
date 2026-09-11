"""Merged knowledge pack for CognitiveTurnKernel KNOWLEDGE stage."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_CATALOG_HINT = (
    "ActionSpecs are the capability ontology: tool/action keys resolve through "
    "the connector action catalog (ActionSpec matrix), not free-form tool names."
)


async def merge(
    *,
    client: Any,
    org_id: str,
    query: str,
    agent: dict[str, Any] | None,
    settings: Settings | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Merge Knowledge Fabric retrieval + entity graph section + catalog hints.

    Always scoped to ``org_id``. Best-effort: missing deps or table errors yield
    empty fabric/entity sections without raising.
    """
    _ = user_id
    active = settings or get_settings()
    if not org_id:
        return _empty_pack()

    fabric_chunks: list[dict[str, Any]] = []
    fabric_route: dict[str, Any] | None = None
    try:
        from app.knowledge_fabric.router import classify_knowledge_query
        from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric

        agent_dept = None
        if isinstance(agent, dict):
            agent_dept = agent.get("department") or (agent.get("config") or {}).get("department")
        route = classify_knowledge_query(query or "", agent_department=agent_dept)
        fabric_route = route.to_dict() if hasattr(route, "to_dict") else None
        retrieved = retrieve_knowledge_fabric(
            client,
            query or "",
            route=route,
            agent_department=str(agent_dept) if agent_dept else None,
            settings=active,
        )
        if isinstance(retrieved, dict):
            fabric_chunks = list(retrieved.get("results") or [])
            if fabric_route is None and isinstance(retrieved.get("route"), dict):
                fabric_route = retrieved.get("route")
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_knowledge_fabric_skipped error=%s", exc)

    entity_section = ""
    try:
        from app.services.entity_relationship_service import build_entity_context_section

        entity_section = await build_entity_context_section(
            org_id,
            query or "",
            settings=active,
            client=client,
        )
        entity_section = entity_section or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_knowledge_entity_skipped error=%s", exc)

    graph_nodes: list[dict[str, Any]] = []
    graph_edges: list[dict[str, Any]] = []
    if client is not None:
        try:
            nodes = (
                client.table("org_knowledge_nodes")
                .select("id,org_id,node_type,name,attributes")
                .eq("org_id", org_id)
                .limit(40)
                .execute()
                .data
                or []
            )
            graph_nodes = [n for n in nodes if str(n.get("org_id") or "") == org_id]
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_knowledge_nodes_skipped error=%s", exc)
        try:
            # Columns match org_entity_relationships migration (no metadata column).
            edges = (
                client.table("org_entity_relationships")
                .select(
                    "id,org_id,source_entity_type,source_entity_id,"
                    "target_entity_type,target_entity_id,relationship_type,confidence"
                )
                .eq("org_id", org_id)
                .limit(40)
                .execute()
                .data
                or []
            )
            graph_edges = [e for e in edges if str(e.get("org_id") or "") == org_id]
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_knowledge_edges_skipped error=%s", exc)

    graph_section = ""
    if graph_nodes or graph_edges:
        lines = ["<org_knowledge_graph>"]
        for n in graph_nodes[:12]:
            # Typed nodes must appear in the prompt for KNOWLEDGE stage.
            attrs = n.get("attributes") if isinstance(n.get("attributes"), dict) else {}
            attr_hint = ""
            if attrs:
                # Compact non-secret attribute keys for grounding (no PII dump).
                keys = ",".join(sorted(str(k) for k in list(attrs.keys())[:4]))
                if keys:
                    attr_hint = f" attrs={keys}"
            lines.append(f"- node:{n.get('node_type')}:{n.get('name')}{attr_hint}")
        for e in graph_edges[:12]:
            lines.append(
                f"- edge:{e.get('relationship_type')} "
                f"{e.get('source_entity_type')}:{e.get('source_entity_id')}→"
                f"{e.get('target_entity_type')}:{e.get('target_entity_id')}"
            )
        lines.append("</org_knowledge_graph>")
        graph_section = "\n".join(lines)
        if graph_section:
            entity_section = "\n\n".join(p for p in (entity_section, graph_section) if p)

    catalog_hints = [{"note": _CATALOG_HINT}]
    prompt_section = _build_prompt_section(fabric_chunks, entity_section, catalog_hints)

    pack: dict[str, Any] = {
        "fabric_chunks": fabric_chunks,
        "fabric_route": fabric_route,
        "entity_section": entity_section,
        "entity_graph": entity_section,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "catalog_hints": catalog_hints,
        "prompt_section": prompt_section,
    }
    pack = await _attach_signal_scoring(
        pack,
        client=client,
        org_id=org_id,
        query=query or "",
        agent=agent,
        settings=active,
    )
    pack = await _attach_sufficiency(
        pack,
        query=query or "",
        settings=active,
        org_id=org_id,
    )
    return pack


def _empty_pack() -> dict[str, Any]:
    return {
        "fabric_chunks": [],
        "fabric_route": None,
        "entity_section": "",
        "entity_graph": "",
        "graph_nodes": [],
        "graph_edges": [],
        "catalog_hints": [{"note": _CATALOG_HINT}],
        "prompt_section": "",
    }


def _build_prompt_section(
    fabric_chunks: list[dict[str, Any]],
    entity_section: str,
    catalog_hints: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    if fabric_chunks:
        lines = ["<knowledge_fabric>"]
        for idx, chunk in enumerate(fabric_chunks[:6], start=1):
            if not isinstance(chunk, dict):
                continue
            snippet = str(
                chunk.get("content")
                or chunk.get("text")
                or chunk.get("snippet")
                or ""
            )[:400]
            if snippet:
                lines.append(f"[{idx}] {snippet}")
        lines.append("</knowledge_fabric>")
        if len(lines) > 2:
            parts.append("\n".join(lines))
    if entity_section and entity_section.strip():
        parts.append(entity_section.strip())
    if catalog_hints:
        note = catalog_hints[0].get("note") if isinstance(catalog_hints[0], dict) else None
        if note:
            parts.append(f"<capability_ontology>\n{note}\n</capability_ontology>")
    return "\n\n".join(parts)


async def _attach_signal_scoring(
    pack: dict[str, Any],
    *,
    client: Any,
    org_id: str,
    query: str,
    agent: dict[str, Any] | None,
    settings: Settings,
) -> dict[str, Any]:
    """Explainable multi-source scores into RETRIEVE so PLAN can cite them.

    Reuses the existing department_signal_scoring_service. Never invents a
    score when WorkObjects or sources are missing — gaps stay explicit.
    """
    try:
        from app.services.unified_turn_knowledge_context import should_include_signal_priorities
    except Exception:  # noqa: BLE001
        return pack
    if not should_include_signal_priorities(query):
        return pack
    if client is None or not org_id:
        pack["signal_scoring"] = {"skipped": "no_client_or_org", "priorities": [], "gaps": ["Scoring needs an org-scoped client."]}
        return pack
    try:
        import asyncio

        from app.services.department_signal_scoring_service import (
            get_department_signal_scoring_service,
        )

        dept = None
        if isinstance(agent, dict):
            dept = str(agent.get("department") or (agent.get("config") or {}).get("department") or "").strip().lower()
        scorer = get_department_signal_scoring_service(settings)
        if dept in {"sales", "marketing", "finance", "hr", "msp"}:
            payload = await asyncio.to_thread(
                scorer.score_department,
                org_id,
                client=client,
                department=dept,
                limit=5,
            )
        else:
            payload = await asyncio.to_thread(
                scorer.score_department,
                org_id,
                client=client,
                department="sales",
                limit=5,
            )
            payload = dict(payload)
            payload.setdefault("gaps", [])
            if not dept:
                payload["gaps"] = list(payload.get("gaps") or []) + [
                    "Department not classified; scored Sales (hiring / tech-adoption / engagement) as the default operator priority surface."
                ]
        pack["signal_scoring"] = payload
        rendered = scorer.render_priority_context(payload)
        if rendered:
            section = str(pack.get("prompt_section") or "")
            block = f"<signal_intelligence>\n{rendered}\nScores are source-cited contributions, not an opaque rank.\n</signal_intelligence>"
            pack["prompt_section"] = f"{section}\n\n{block}".strip() if section else block
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_signal_scoring_skipped error=%s", exc)
        pack["signal_scoring"] = {"ok": False, "error": str(exc)[:200], "priorities": [], "gaps": ["Signal scoring failed open."]}
    return pack


async def _attach_sufficiency(
    pack: dict[str, Any],
    *,
    query: str,
    settings: Settings,
    org_id: str,
) -> dict[str, Any]:
    """Resume sufficiency-gated retrieval (CRAG) on the kernel RETRIEVE path.

    The loop already exists in unified_turn_knowledge_context. Kernel merge
    used to retrieve once and stop. Operator-task and prioritization turns now
    get a real sufficiency verdict on the same fabric rows; additional internet
    rounds stay on the unified-turn path to avoid a second retrieval stack.
    """
    if not getattr(settings, "evidence_sufficiency_loop_enabled", True):
        pack["sufficiency"] = {"skipped": "flag_disabled"}
        return pack
    try:
        from app.services.evidence_sufficiency_service import (
            BAR_CASUAL,
            assess_evidence_sufficiency,
            sufficiency_bar_for,
        )
        from app.services.operator_task_intent import is_operator_task_shaped
        from app.services.unified_turn_knowledge_context import should_include_signal_priorities

        if not (is_operator_task_shaped(query) or should_include_signal_priorities(query)):
            pack["sufficiency"] = {"skipped": "not_operator_or_priority"}
            return pack
        bar = sufficiency_bar_for(query=query, route_departments=[], route_jurisdictions=[], reasoning_depth="full")
        if bar.name == BAR_CASUAL:
            pack["sufficiency"] = {"skipped": "casual_bar", "bar": bar.name}
            return pack
        rows = []
        for chunk in list(pack.get("fabric_chunks") or [])[:8]:
            if not isinstance(chunk, dict):
                continue
            rows.append(
                {
                    "content": str(chunk.get("content") or chunk.get("text") or chunk.get("snippet") or ""),
                    "score": chunk.get("score") or 0.5,
                    "source": chunk.get("source") or chunk.get("source_id"),
                }
            )
        verdict = await assess_evidence_sufficiency(
            query=query,
            rows=rows,
            bar=bar,
            settings=settings,
            org_id=org_id,
            routing_tier="multi_step",
            sources_tried=["knowledge_fabric"],
        )
        pack["sufficiency"] = verdict.to_dict() if hasattr(verdict, "to_dict") else {"sufficient": bool(getattr(verdict, "sufficient", False))}
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_sufficiency_skipped error=%s", exc)
        pack["sufficiency"] = {"skipped": "assessor_error", "error": str(exc)[:200]}
    return pack
