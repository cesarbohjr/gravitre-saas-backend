"use client"

import type { CSSProperties } from "react"
import type { IntelligenceCoreDepartment } from "@/lib/api"
import { MAP_KIND_NUCLEO, NodusGraphNodeTile } from "@/components/intelligence/graph/nodus-graph-node"
import { formatDepartmentLabel } from "./types"
import { cn } from "@/lib/utils"

const STATE_COPY: Record<IntelligenceCoreDepartment["state"], string> = {
  idle: "Idle",
  "flow-inward": "New activity",
  trace: "Active",
  "pending-approval": "Awaiting approval",
  resolved: "Resolved",
  "low-confidence": "Low confidence",
}

/**
 * Department node — same Nodus square-tile language as connectors/agents graphs.
 */
export function DepartmentNode({
  department,
  reduced = false,
  style,
  embedded = false,
}: {
  department: IntelligenceCoreDepartment
  reduced?: boolean
  style?: CSSProperties
  /** When true, parent handles positioning (map click targets). */
  embedded?: boolean
}) {
  const isActive = department.state === "flow-inward" || department.state === "trace"
  const Icon = MAP_KIND_NUCLEO.department

  return (
    <div
      className={cn(!embedded && "absolute -translate-x-1/2 -translate-y-1/2")}
      style={style}
    >
      <NodusGraphNodeTile
        icon={Icon}
        label={formatDepartmentLabel(department.id)}
        sublabel={
          department.eventsInWindow > 0
            ? `${STATE_COPY[department.state]} · ${department.eventsInWindow}`
            : STATE_COPY[department.state]
        }
        active={isActive}
        working={isActive}
        reduced={reduced}
      />
    </div>
  )
}
