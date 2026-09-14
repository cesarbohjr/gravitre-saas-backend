"""G1 — Build IntelligenceGraph from canonical IntelligenceSnapshot."""
from __future__ import annotations

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


def build_intelligence_graph(snapshot: IntelligenceSnapshot) -> IntelligenceGraph:
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
                metadata={"entityType": et},
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
