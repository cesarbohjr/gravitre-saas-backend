/**
 * G4 — Canonical Ask Gravitre → Intelligence Map visualization contract.
 * Parses backend `AssistantVisualization` from SSE and maps it to map UI state.
 */
import type { IntelligenceCoreDepartment } from "@/lib/api"
import type { Agent } from "@/types/api"
import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import { readString } from "@/lib/intelligence/helpers"

export type AssistantVisualization = {
  lens?: IntelligenceMapLens | null
  focusNodeIds?: string[]
  highlightNodeIds?: string[]
  dimNodeIds?: string[]
  expandNodeIds?: string[]
  edgeTypes?: string[]
  timeWindowHours?: number | null
}

const VALID_LENSES = new Set<IntelligenceMapLens>([
  "knows",
  "learns",
  "predicts",
  "acts",
  "improves",
])

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.length > 0)
}

/** Parse visualization payload from `data-intelligence` SSE events. */
export function parseAssistantVisualization(raw: unknown): AssistantVisualization | null {
  if (!raw || typeof raw !== "object") return null
  const record = raw as Record<string, unknown>
  const lensRaw = record.lens
  const lens =
    typeof lensRaw === "string" && VALID_LENSES.has(lensRaw as IntelligenceMapLens)
      ? (lensRaw as IntelligenceMapLens)
      : null
  const focusNodeIds = readStringArray(record.focusNodeIds)
  const highlightNodeIds = readStringArray(record.highlightNodeIds)
  const dimNodeIds = readStringArray(record.dimNodeIds)
  const expandNodeIds = readStringArray(record.expandNodeIds)
  const edgeTypes = readStringArray(record.edgeTypes)
  const timeWindowHours =
    typeof record.timeWindowHours === "number" && Number.isFinite(record.timeWindowHours)
      ? record.timeWindowHours
      : null

  if (
    !lens &&
    focusNodeIds.length === 0 &&
    highlightNodeIds.length === 0 &&
    dimNodeIds.length === 0 &&
    expandNodeIds.length === 0 &&
    edgeTypes.length === 0 &&
    timeWindowHours == null
  ) {
    return null
  }

  return {
    lens,
    focusNodeIds,
    highlightNodeIds,
    dimNodeIds,
    expandNodeIds,
    edgeTypes,
    timeWindowHours,
  }
}

/** Keep only node ids that exist on the current canonical graph. */
export function filterNodeIdsToGraph(nodeIds: string[], graphNodeIds: Set<string>): string[] {
  return nodeIds.filter((id) => graphNodeIds.has(id))
}

function resolveSelectionFromNodeId(
  nodeId: string,
  context: {
    agents: Agent[]
    departments: IntelligenceCoreDepartment[]
    signals: Record<string, unknown>[]
  },
): IntelligenceMapSelection {
  if (nodeId.startsWith("agent:")) {
    const agentId = nodeId.slice("agent:".length)
    const agent = context.agents.find((a) => a.id === agentId)
    if (agent) return { kind: "agent", agent }
  }

  if (nodeId.startsWith("dept:")) {
    const deptId = nodeId.slice("dept:".length)
    const department = context.departments.find(
      (d) => d.id.toLowerCase() === deptId.toLowerCase(),
    )
    if (department) return { kind: "department", department }
  }

  if (nodeId.startsWith("prediction:") || nodeId.startsWith("signal:")) {
    const rawId = nodeId.includes(":") ? nodeId.split(":").slice(1).join(":") : nodeId
    const signal =
      context.signals.find(
        (s) =>
          readString(s.id, "") === rawId ||
          readString(s.id, "") === nodeId ||
          `prediction:${readString(s.id, "")}` === nodeId,
      ) ?? {
        id: rawId,
        title: rawId,
      }
    return { kind: "signal", signal }
  }

  return null
}

export type MapVisualizationState = {
  lens?: IntelligenceMapLens
  highlightNodeIds: string[]
  dimNodeIds: string[]
  focusNodeIds: string[]
  selection: IntelligenceMapSelection
}

/**
 * Convert canonical backend visualization intent into map-ready state.
 * Node ids are validated against the current page-context graph when provided.
 */
export function applyAssistantVisualizationToMapState(
  viz: AssistantVisualization,
  context: {
    graphNodeIds?: Set<string>
    agents: Agent[]
    departments: IntelligenceCoreDepartment[]
    signals: Record<string, unknown>[]
  },
): MapVisualizationState {
  const graphIds = context.graphNodeIds
  const filter = (ids: string[]) => (graphIds ? filterNodeIdsToGraph(ids, graphIds) : ids)

  const highlightNodeIds = filter(viz.highlightNodeIds ?? [])
  const dimNodeIds = filter(viz.dimNodeIds ?? [])
  const focusNodeIds = filter(viz.focusNodeIds ?? [])

  const selectionSource =
    focusNodeIds[0] ?? highlightNodeIds[0] ?? null
  const selection = selectionSource
    ? resolveSelectionFromNodeId(selectionSource, context)
    : null

  return {
    lens: viz.lens ?? undefined,
    highlightNodeIds,
    dimNodeIds,
    focusNodeIds: focusNodeIds.length > 0 ? focusNodeIds : highlightNodeIds,
    selection,
  }
}
