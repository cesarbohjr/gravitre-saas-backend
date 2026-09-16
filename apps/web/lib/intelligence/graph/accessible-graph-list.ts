/**
 * I10 — DOM list alternative for the same IntelligenceGraph topology.
 */
import type { MapTopology } from "@/components/intelligence/map/map-topology"

export type AccessibleGraphRow = {
  id: string
  kind: string
  label: string
  sublabel?: string
}

export function accessibleGraphRows(topology: MapTopology | null | undefined): AccessibleGraphRow[] {
  if (!topology?.nodes?.length) return []
  return topology.nodes.map((node) => ({
    id: node.id,
    kind: node.kind.replace(/-/g, " "),
    label: node.label,
    sublabel: node.sublabel,
  }))
}
