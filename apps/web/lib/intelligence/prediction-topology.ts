/**
 * I6 — Risk / opportunity topology layout (pure, testable).
 */
import type { BusinessPredictionDisplay } from "@/lib/intelligence/prediction-display"

export type PredictionTopologyNode = {
  id: string
  label: string
  kind: "hub" | "risk" | "opportunity" | "signal"
  confidence?: number | null
}

export type PredictionTopologyEdge = {
  id: string
  fromId: string
  toId: string
}

export type PredictionTopologyLayout = {
  nodes: PredictionTopologyNode[]
  edges: PredictionTopologyEdge[]
  positions: Map<string, { x: number; y: number }>
}

export const PREDICTION_TOPOLOGY_VB = { w: 640, h: 280 }

const HUB_ID = "hub:horizon"

function truncate(label: string, max = 32): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

export function buildPredictionTopology(
  risks: BusinessPredictionDisplay[],
  opportunities: BusinessPredictionDisplay[],
  signals: BusinessPredictionDisplay[],
  maxPerSide = 4,
): Omit<PredictionTopologyLayout, "positions"> {
  const nodes: PredictionTopologyNode[] = [
    { id: HUB_ID, label: "Prediction horizon", kind: "hub" },
  ]
  const edges: PredictionTopologyEdge[] = []

  risks.slice(0, maxPerSide).forEach((row, index) => {
    const id = `risk:${row.id || index}`
    nodes.push({
      id,
      label: truncate(row.statement),
      kind: "risk",
      confidence: row.confidence,
    })
    edges.push({ id: `edge:${id}:${HUB_ID}`, fromId: id, toId: HUB_ID })
  })

  opportunities.slice(0, maxPerSide).forEach((row, index) => {
    const id = `opp:${row.id || index}`
    nodes.push({
      id,
      label: truncate(row.statement),
      kind: "opportunity",
      confidence: row.confidence,
    })
    edges.push({ id: `edge:${HUB_ID}:${id}`, fromId: HUB_ID, toId: id })
  })

  signals.slice(0, 2).forEach((row, index) => {
    const id = `sig:${row.id || index}`
    nodes.push({
      id,
      label: truncate(row.statement),
      kind: "signal",
      confidence: row.confidence,
    })
    edges.push({ id: `edge:${HUB_ID}:${id}`, fromId: HUB_ID, toId: id })
  })

  return { nodes, edges }
}

export function layoutPredictionTopology(
  graph: Omit<PredictionTopologyLayout, "positions">,
): PredictionTopologyLayout {
  const { w, h } = PREDICTION_TOPOLOGY_VB
  const positions = new Map<string, { x: number; y: number }>()
  positions.set(HUB_ID, { x: w / 2, y: h / 2 })

  const left = graph.nodes.filter((n) => n.kind === "risk")
  const right = graph.nodes.filter((n) => n.kind === "opportunity" || n.kind === "signal")

  left.forEach((node, index) => {
    const total = Math.max(left.length, 1)
    const y = ((index + 1) / (total + 1)) * h
    positions.set(node.id, { x: w * 0.14, y })
  })

  right.forEach((node, index) => {
    const total = Math.max(right.length, 1)
    const y = ((index + 1) / (total + 1)) * h
    positions.set(node.id, { x: w * 0.86, y })
  })

  return { ...graph, positions }
}
