"use client"

import type { MapNode } from "./map-topology"
import { MAP_KIND_NUCLEO, NodusGraphNodeTile } from "@/components/intelligence/graph/nodus-graph-node"

export function MapSatelliteNode({
  node,
  reduced = false,
  selected = false,
  showLabel = true,
}: {
  node: MapNode
  reduced?: boolean
  selected?: boolean
  showLabel?: boolean
}) {
  const isActive = node.emphasis >= 0.85
  const Icon = MAP_KIND_NUCLEO[node.kind]

  return (
    <div>
      <NodusGraphNodeTile
        icon={Icon}
        label={node.label}
        sublabel={node.sublabel}
        active={isActive}
        selected={selected}
        showLabel={showLabel}
        size="sm"
        reduced={reduced}
      />
    </div>
  )
}
