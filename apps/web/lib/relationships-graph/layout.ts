import dagre from "@dagrejs/dagre"
import { Position, type Edge, type Node } from "@xyflow/react"
import type { GraphEdgeData, GraphNodeData } from "./types"

const NODE_WIDTH = 196
const NODE_HEIGHT = 68

export function layoutGraphElements(
  nodes: Node<GraphNodeData>[],
  edges: Edge<GraphEdgeData>[],
): { nodes: Node<GraphNodeData>[]; edges: Edge<GraphEdgeData>[] } {
  if (nodes.length === 0) {
    return { nodes, edges }
  }

  const graph = new dagre.graphlib.Graph()
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({ rankdir: "LR", nodesep: 48, ranksep: 72, marginx: 24, marginy: 24 })

  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target)
  }

  dagre.layout(graph)

  const layoutedNodes = nodes.map((node) => {
    const pos = graph.node(node.id)
    return {
      ...node,
      position: {
        x: (pos?.x ?? 0) - NODE_WIDTH / 2,
        y: (pos?.y ?? 0) - NODE_HEIGHT / 2,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }
  })

  return { nodes: layoutedNodes, edges }
}
