/**
 * I8 — Usage topology for the Models catalog (models only — no invented callers).
 */
import type { ModelCatalogDisplay } from "@/lib/intelligence/model-catalog-display"

export type ModelUsageNode = {
  id: string
  label: string
  kind: "hub" | "in_use" | "not_in_use"
}

export type ModelUsageEdge = { id: string; fromId: string; toId: string }

export const MODEL_USAGE_VB = { w: 640, h: 260 }
const HUB_ID = "hub:usage"

function truncate(label: string, max = 28): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label
}

export function buildModelUsageTopology(models: ModelCatalogDisplay[], maxNodes = 8) {
  const nodes: ModelUsageNode[] = [{ id: HUB_ID, label: "Where models are used", kind: "hub" }]
  const edges: ModelUsageEdge[] = []
  models.slice(0, maxNodes).forEach((model) => {
    const inUse = model.whereUsed.startsWith("Available")
    const id = `model:${model.id}`
    nodes.push({
      id,
      label: truncate(model.name),
      kind: inUse ? "in_use" : "not_in_use",
    })
    edges.push({ id: `edge:${HUB_ID}:${id}`, fromId: HUB_ID, toId: id })
  })
  return { nodes, edges }
}

export function layoutModelUsageTopology(graph: ReturnType<typeof buildModelUsageTopology>) {
  const { w, h } = MODEL_USAGE_VB
  const positions = new Map<string, { x: number; y: number }>()
  positions.set(HUB_ID, { x: w / 2, y: h / 2 })
  const satellites = graph.nodes.filter((n) => n.kind !== "hub")
  satellites.forEach((node, index) => {
    const total = Math.max(satellites.length, 1)
    const angle = (index / total) * Math.PI * 2 - Math.PI / 2
    positions.set(node.id, {
      x: w / 2 + Math.cos(angle) * w * 0.34,
      y: h / 2 + Math.sin(angle) * h * 0.36,
    })
  })
  return { ...graph, positions }
}
