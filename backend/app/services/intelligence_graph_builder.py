"""G1 — Build IntelligenceGraph from canonical IntelligenceSnapshot."""
from __future__ import annotations

from typing import Any

from app.schemas.intelligence_projection import (
    IntelligenceGraph,
    IntelligenceGraphEdge,
    IntelligenceGraphNode,
    IntelligenceLensId,
    IntelligenceProvenance,
    IntelligenceSnapshot,
)
from app.services.intelligence_semantics import LENS_EDGE_EMPHASIS, LENS_NODE_EMPHASIS, model_business_label

CORE_NODE_ID = "core:gravitre"


def _opaque_entity_label(entity_type: str, entity_id: str) -> str:
    """Honest label: type + short opaque suffix — never invent CRM display names."""
    et = (entity_type or "entity").replace("_", " ").strip() or "entity"
    suffix = entity_id[-6:] if len(entity_id) > 6 else entity_id
    return f"{et.title()} · …{suffix}"


def _entity_node_id(entity_type: str, entity_id: str) -> str:
    et = (entity_type or "entity").strip().lower().replace(" ", "_") or "entity"
    return f"kg:{et}:{entity_id}"


def build_intelligence_graph(
    snapshot: IntelligenceSnapshot,
    *,
    field_sample: list[dict[str, Any]] | None = None,
) -> IntelligenceGraph:
    nodes: list[IntelligenceGraphNode] = []
    edges: list[IntelligenceGraphEdge] = []
    node_ids: set[str] = set()

    def add_node(node: IntelligenceGraphNode) -> None:
        if node.id in node_ids:
            return
        node_ids.add(node.id)
        nodes.append(node)

    add_node(
        IntelligenceGraphNode(
            id=CORE_NODE_ID,
            type="core",
            businessLabel="Gravitre Intelligence",
            status=snapshot.coreState,
            source=IntelligenceProvenance(
                system="intelligence_projection",
                recordId=snapshot.tenantId,
                fetchedAt=snapshot.generatedAt,
            ),
            metadata={"timeWindowHours": snapshot.timeWindowHours},
        )
    )

    # I1 field — real org_entity_relationships endpoints (when ids resolve)
    for row in field_sample or []:
        sid = str(row.get("source_entity_id") or "").strip()
        tid = str(row.get("target_entity_id") or "").strip()
        if not sid or not tid:
            continue
        st = str(row.get("source_entity_type") or "entity")
        tt = str(row.get("target_entity_type") or "entity")
        rel_type = str(row.get("relationship_type") or "related")
        src_id = _entity_node_id(st, sid)
        tgt_id = _entity_node_id(tt, tid)
        add_node(
            IntelligenceGraphNode(
                id=src_id,
                type="entity",
                businessLabel=_opaque_entity_label(st, sid),
                technicalLabel=sid,
                status="active",
                source=IntelligenceProvenance(
                    system="org_entity_relationships",
                    recordId=sid,
                    fetchedAt=snapshot.generatedAt,
                ),
                freshness=str(row.get("updated_at") or "") or None,
                metadata={
                    "entityType": st,
                    "entityId": sid,
                    "instance": True,
                    "confidence": row.get("confidence"),
                },
            )
        )
        add_node(
            IntelligenceGraphNode(
                id=tgt_id,
                type="entity",
                businessLabel=_opaque_entity_label(tt, tid),
                technicalLabel=tid,
                status="active",
                source=IntelligenceProvenance(
                    system="org_entity_relationships",
                    recordId=tid,
                    fetchedAt=snapshot.generatedAt,
                ),
                freshness=str(row.get("updated_at") or "") or None,
                metadata={
                    "entityType": tt,
                    "entityId": tid,
                    "instance": True,
                    "confidence": row.get("confidence"),
                },
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:kg:{src_id}:{tgt_id}:{rel_type}",
                type="RELATED_TO",
                fromId=src_id,
                toId=tgt_id,
                metadata={
                    "relationshipType": rel_type,
                    "confidence": row.get("confidence"),
                    "evidence": row.get("evidence"),
                    "instance": True,
                },
            )
        )

    for entity_type in snapshot.knowledgeEntityTypes:
        et = str(entity_type or "").strip()
        if not et:
            continue
        nid = f"entity:{et}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="entity",
                businessLabel=et.replace("_", " ").title(),
                technicalLabel=et,
                status="active",
                source=IntelligenceProvenance(
                    system="knowledge_graph",
                    recordId=et,
                    fetchedAt=snapshot.generatedAt,
                ),
                metadata={"entityType": et, "instance": False},
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="KNOWS",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )

    for dept in snapshot.departments:
        dept_id = str(dept.get("id") or "")
        if not dept_id:
            continue
        nid = f"dept:{dept_id}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="domain",
                businessLabel=dept_id.replace("_", " ").title(),
                status=str(dept.get("state") or "idle"),
                source=IntelligenceProvenance(
                    system="intelligence_outcome_events",
                    recordId=dept_id,
                    fetchedAt=snapshot.generatedAt,
                ),
                metadata={
                    "eventsInWindow": dept.get("eventsInWindow"),
                    "recentResolved": dept.get("recentResolved"),
                },
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="KNOWS",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )

    for agent in snapshot.agents:
        nid = f"agent:{agent.id}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="agent",
                businessLabel=agent.businessLabel,
                technicalLabel=agent.technicalLabel,
                status=agent.configuredStatus,
                source=agent.source,
                metadata={
                    "department": agent.department,
                    "isConfiguredActive": agent.isConfiguredActive,
                    "isCurrentlyRunning": agent.isCurrentlyRunning,
                    "executionStatus": agent.executionStatus,
                },
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="ASSIGNED_TO",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )
        if agent.department:
            dept_nid = f"dept:{agent.department.lower().replace(' ', '_')}"
            if dept_nid in node_ids:
                edges.append(
                    IntelligenceGraphEdge(
                        id=f"edge:{nid}:{dept_nid}",
                        type="USED_BY",
                        fromId=nid,
                        toId=dept_nid,
                    )
                )

    for prediction in snapshot.predictions:
        nid = f"prediction:{prediction.id}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="prediction",
                businessLabel=prediction.businessStatement[:120],
                technicalLabel=prediction.sourceModel,
                status=prediction.status,
                source=prediction.source,
                metadata={"confidence": prediction.confidence, "department": prediction.department},
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="PREDICTS",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )
        if prediction.department:
            dept_nid = f"dept:{prediction.department.lower().replace(' ', '_')}"
            if dept_nid in node_ids:
                edges.append(
                    IntelligenceGraphEdge(
                        id=f"edge:{nid}:{dept_nid}",
                        type="AFFECTS",
                        fromId=nid,
                        toId=dept_nid,
                    )
                )

    for model in snapshot.models:
        slug = str(model.get("id") or model.get("modelId") or "")
        if not slug:
            continue
        nid = f"model:{slug}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="model",
                businessLabel=str(model.get("businessLabel") or model_business_label(slug)),
                technicalLabel=slug,
                status=str(model.get("status") or "unknown"),
                source=IntelligenceProvenance(
                    system="model_catalog",
                    recordId=slug,
                    fetchedAt=snapshot.generatedAt,
                ),
                metadata=model,
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="LEARNED_FROM",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )

    for insight in snapshot.learnings:
        nid = f"learning:{insight.id}"
        add_node(
            IntelligenceGraphNode(
                id=nid,
                type="learning",
                businessLabel=insight.businessStatement[:120],
                status="learned",
                source=insight.source,
                metadata={"confidence": insight.confidence},
            )
        )
        edges.append(
            IntelligenceGraphEdge(
                id=f"edge:core:{nid}",
                type="IMPROVED",
                fromId=CORE_NODE_ID,
                toId=nid,
            )
        )

    return IntelligenceGraph(nodes=nodes, edges=edges)


def filter_graph_for_lens(graph: IntelligenceGraph, lens: IntelligenceLensId) -> IntelligenceGraph:
    """Lens projection — same graph, filtered emphasis (not a separate topology)."""
    node_types = LENS_NODE_EMPHASIS.get(lens, set())
    edge_types = LENS_EDGE_EMPHASIS.get(lens, set())
    nodes = [n for n in graph.nodes if n.type in node_types or n.type == "core"]
    allowed_ids = {n.id for n in nodes}
    edges = [
        e
        for e in graph.edges
        if e.type in edge_types and e.fromId in allowed_ids and e.toId in allowed_ids
    ]
    return IntelligenceGraph(nodes=nodes, edges=edges)
