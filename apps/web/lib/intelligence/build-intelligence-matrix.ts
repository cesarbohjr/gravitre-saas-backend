import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import { INTELLIGENCE_MAP_LENSES } from "@/components/intelligence/map/intelligence-map-lens"
import type { CanonicalGraphNode } from "@/lib/intelligence/canonical-graph-topology"
import { nodeMatchesLens } from "@/lib/intelligence/lens-node-emphasis"

export type IntelligenceMatrixRowId = "agents" | "sources" | "connectors" | "outcomes" | "knowledge"

export const INTELLIGENCE_MATRIX_ROWS: Array<{ id: IntelligenceMatrixRowId; label: string }> = [
  { id: "agents", label: "Agents" },
  { id: "sources", label: "Sources" },
  { id: "connectors", label: "Connectors" },
  { id: "outcomes", label: "Outcomes" },
  { id: "knowledge", label: "Knowledge" },
]

export type IntelligenceMatrixCell = {
  rowId: IntelligenceMatrixRowId
  lens: IntelligenceMapLens
  count: number
  topSignal: string | null
  nodeIds: string[]
}

export type IntelligenceMatrixModel = {
  cells: IntelligenceMatrixCell[]
  byKey: Map<string, IntelligenceMatrixCell>
}

function matrixRowForNode(node: CanonicalGraphNode): IntelligenceMatrixRowId | null {
  if (node.type === "core") return null
  if (node.type === "agent") return "agents"
  if (node.type === "connector") return "connectors"
  if (node.type === "outcome") return "outcomes"

  const entityType = String(node.metadata?.entityType ?? node.technicalLabel ?? "").toLowerCase()
  const sourceSystem = String(
    (node.metadata?.source as { system?: string } | undefined)?.system ??
      node.metadata?.system ??
      "",
  ).toLowerCase()

  if (node.type === "entity") {
    if (entityType.includes("source") || sourceSystem.includes("source")) return "sources"
    return "knowledge"
  }

  if (["knowledge", "domain", "model", "learning", "prediction"].includes(node.type)) {
    return "knowledge"
  }

  return "knowledge"
}

function topSignalLabel(nodes: CanonicalGraphNode[]): string | null {
  const ranked = nodes.find((n) => n.type === "prediction" || n.type === "learning")
  return ranked ? ranked.businessLabel.slice(0, 48) : null
}

export function buildIntelligenceMatrix(
  nodes: CanonicalGraphNode[] | undefined | null,
): IntelligenceMatrixModel {
  const graphNodes = (nodes ?? []).filter((n) => n.type !== "core")
  const cells: IntelligenceMatrixCell[] = []

  for (const row of INTELLIGENCE_MATRIX_ROWS) {
    for (const lensDef of INTELLIGENCE_MAP_LENSES) {
      const lens = lensDef.id
      const matched = graphNodes.filter(
        (node) => matrixRowForNode(node) === row.id && nodeMatchesLens(node.type, lens),
      )
      cells.push({
        rowId: row.id,
        lens,
        count: matched.length,
        topSignal: topSignalLabel(matched),
        nodeIds: matched.map((n) => n.id),
      })
    }
  }

  const byKey = new Map(cells.map((cell) => [`${cell.rowId}:${cell.lens}`, cell]))
  return { cells, byKey }
}

export function matrixCellKey(rowId: IntelligenceMatrixRowId, lens: IntelligenceMapLens): string {
  return `${rowId}:${lens}`
}
