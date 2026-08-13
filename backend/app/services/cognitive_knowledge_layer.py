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

    return {
        "fabric_chunks": fabric_chunks,
        "fabric_route": fabric_route,
        "entity_section": entity_section,
        "entity_graph": entity_section,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "catalog_hints": catalog_hints,
        "prompt_section": prompt_section,
    }


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
