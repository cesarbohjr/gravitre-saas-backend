"use client"

import { memo, useCallback, useEffect, useMemo, type CSSProperties } from "react"
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type OnSelectionChangeParams,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { applyEdgeAggregation } from "@/lib/relationships-graph/aggregate-edges"
import { layoutGraphElements } from "@/lib/relationships-graph/layout"
import {
  buildGraphNodeData,
  entityKey,
  knowledgeNodeLabel,
  readNumber,
  relationshipEdgeId,
  relationshipTypeDisplay,
  seededNodeKey,
} from "@/lib/relationships-graph/utils"
import type { GraphEdgeData, GraphNodeData, RelationshipRow } from "@/lib/relationships-graph/types"
import { relationshipNodeTypes } from "./relationship-graph-node"
import { RelationshipLegend } from "./relationship-legend"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

function edgeStyle(rel: RelationshipRow, confidence: number): CSSProperties | undefined {
  if (rel.archived_at) return { opacity: 0.4, strokeDasharray: "5 4" }
  if (confidence < 0.5) return { strokeDasharray: "4 3", stroke: "var(--g-warning, #d97706)" }
  return undefined
}

function buildElements(
  filtered: RelationshipRow[],
  nodes: RelationshipRow[],
  labelFor: (entityType: unknown, entityId: unknown) => string,
): { nodes: Node<GraphNodeData>[]; edges: Edge<GraphEdgeData>[] } {
  const nodeMap = new Map<string, Node<GraphNodeData>>()
  const seededIds = new Set(nodes.map((n) => String(n.id ?? "")))

  for (const kn of nodes) {
    const id = String(kn.id ?? "")
    if (!id) continue
    const nodeType = String(kn.node_type ?? "company")
    nodeMap.set(seededNodeKey(id), {
      id: seededNodeKey(id),
      type: "relationshipEntity",
      position: { x: 0, y: 0 },
      data: buildGraphNodeData(nodeType, id, knowledgeNodeLabel(kn), true, id),
    })
  }

  const edges: Edge<GraphEdgeData>[] = []

  for (const rel of filtered) {
    const sourceType = String(rel.source_entity_type ?? "")
    const sourceId = String(rel.source_entity_id ?? "")
    const targetType = String(rel.target_entity_type ?? "")
    const targetId = String(rel.target_entity_id ?? "")
    if (!sourceType || !sourceId || !targetType || !targetId) continue

    const sourceKey = entityKey(sourceType, sourceId)
    const targetKey = entityKey(targetType, targetId)

    if (!nodeMap.has(sourceKey)) {
      nodeMap.set(sourceKey, {
        id: sourceKey,
        type: "relationshipEntity",
        position: { x: 0, y: 0 },
        data: buildGraphNodeData(sourceType, sourceId, labelFor(sourceType, sourceId), false),
      })
    }
    if (!nodeMap.has(targetKey)) {
      nodeMap.set(targetKey, {
        id: targetKey,
        type: "relationshipEntity",
        position: { x: 0, y: 0 },
        data: buildGraphNodeData(targetType, targetId, labelFor(targetType, targetId), false),
      })
    }

    for (const [key, knId] of [
      [sourceKey, sourceId],
      [targetKey, targetId],
    ] as const) {
      if (seededIds.has(knId)) {
        const existing = nodeMap.get(key)
        if (existing) {
          nodeMap.set(key, {
            ...existing,
            data: { ...existing.data, isSeeded: true, knowledgeNodeId: knId },
          })
        }
      }
    }

    const edgeId = relationshipEdgeId(rel)
    const confidence = readNumber(rel.confidence)
    edges.push({
      id: edgeId,
      source: sourceKey,
      target: targetKey,
      label: relationshipTypeDisplay(rel.relationship_type),
      markerEnd: { type: "arrowclosed" as const, width: 16, height: 16 },
      data: {
        relationshipType: String(rel.relationship_type ?? ""),
        relationshipTypeLabel: relationshipTypeDisplay(rel.relationship_type),
        confidence,
        evidenceCount: readNumber(rel.evidence_count),
        archived: Boolean(rel.archived_at),
        relationshipId: String(rel.id ?? ""),
        raw: rel,
      },
      animated: confidence >= 0.75 && !rel.archived_at,
      style: edgeStyle(rel, confidence),
    })
  }

  const rawNodes = [...nodeMap.values()]
  return layoutGraphElements(rawNodes, edges)
}

function RelationshipGraphCanvasInner({ workspace }: { workspace: RelationshipsWorkspaceState }) {
  const { filtered, nodes, labelFor, selection, setSelection, expandedClusters } = workspace

  const elements = useMemo(() => {
    const built = buildElements(filtered, nodes, labelFor)
    const aggregated = applyEdgeAggregation(
      built.nodes,
      built.edges,
      filtered,
      expandedClusters,
      labelFor,
    )
    return layoutGraphElements(aggregated.nodes, aggregated.edges)
  }, [filtered, nodes, labelFor, expandedClusters])

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState(elements.nodes)
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(elements.edges)

  useEffect(() => {
    setFlowNodes(elements.nodes)
    setFlowEdges(elements.edges)
  }, [elements.nodes, elements.edges, setFlowNodes, setFlowEdges])

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes, edges: selectedEdges }: OnSelectionChangeParams) => {
      if (selectedEdges.length > 0) {
        setSelection({ kind: "edge", edgeId: selectedEdges[0].id })
        return
      }
      if (selectedNodes.length > 0) {
        setSelection({ kind: "node", nodeId: selectedNodes[0].id })
        return
      }
      setSelection(null)
    },
    [setSelection],
  )

  useEffect(() => {
    if (!selection) return
    setFlowNodes((nds) =>
      nds.map((n) => ({
        ...n,
        selected: selection.kind === "node" && n.id === selection.nodeId,
      })),
    )
    setFlowEdges((eds) =>
      eds.map((e) => ({
        ...e,
        selected: selection.kind === "edge" && e.id === selection.edgeId,
      })),
    )
  }, [selection, setFlowNodes, setFlowEdges])

  if (filtered.length === 0 && nodes.length === 0) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center p-8 text-center">
        <p className="max-w-md text-sm leading-relaxed text-[color:var(--g-text-muted)]">
          No graph data yet. Add organization knowledge or wait for learned relationships to appear.
        </p>
      </div>
    )
  }

  return (
    <div className="relative h-full min-h-[420px] w-full">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onSelectionChange={onSelectionChange}
        nodeTypes={relationshipNodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        className="bg-[color:var(--g-surface-2)]/30"
      >
        <Background gap={22} size={1} color="var(--divide)" />
        <Controls showInteractive={false} className="!shadow-[var(--np-shadow)]" />
        <MiniMap
          pannable
          zoomable
          className="!rounded-[var(--np-radius-md)] !border-divide !bg-[color:var(--g-surface-1)]/95 !shadow-[var(--np-shadow)]"
          maskColor="rgba(0,0,0,0.06)"
        />
      </ReactFlow>
      <RelationshipLegend />
    </div>
  )
}

export const RelationshipGraphCanvas = memo(function RelationshipGraphCanvas({
  workspace,
}: {
  workspace: RelationshipsWorkspaceState
}) {
  return (
    <ReactFlowProvider>
      <RelationshipGraphCanvasInner workspace={workspace} />
    </ReactFlowProvider>
  )
})
