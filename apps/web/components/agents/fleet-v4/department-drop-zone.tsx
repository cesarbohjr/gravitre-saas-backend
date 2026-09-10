"use client"

import { useState, type DragEvent, type ReactNode } from "react"
import { cn } from "@/lib/utils"
import { DEPARTMENT_ACCENT } from "./identity-tokens"
import {
  FLEET_AGENT_DRAG_MIME,
  getFleetAgentDragData,
  type FleetAgentDragPayload,
} from "./fleet-department-dnd"
import type { AgentDepartmentId } from "./types"

export function DepartmentDropZone({
  department,
  onDropAgent,
  children,
  className,
  highlightClassName,
  label,
}: {
  department: AgentDepartmentId
  onDropAgent?: (agentId: string, department: AgentDepartmentId) => void
  children: ReactNode
  className?: string
  highlightClassName?: string
  /** Optional visible label when empty / for graph lanes */
  label?: ReactNode
}) {
  const [over, setOver] = useState(false)
  const enabled = Boolean(onDropAgent)

  const onDragOver = (e: DragEvent) => {
    if (!enabled) return
    const types = Array.from(e.dataTransfer.types)
    if (!types.includes(FLEET_AGENT_DRAG_MIME) && !types.includes("text/plain")) return
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    setOver(true)
  }

  const onDragLeave = (e: DragEvent) => {
    if (!enabled) return
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setOver(false)
  }

  const onDrop = (e: DragEvent) => {
    if (!enabled || !onDropAgent) return
    e.preventDefault()
    setOver(false)
    const payload: FleetAgentDragPayload | null = getFleetAgentDragData(e.dataTransfer)
    if (!payload?.agentId) return
    if (payload.fromDepartment === department) return
    onDropAgent(payload.agentId, department)
  }

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      data-department-drop={department}
      data-fleet-interactive=""
      className={cn(
        "rounded-[var(--np-radius-md)] transition-[box-shadow,background-color,border-color]",
        over &&
          (highlightClassName ??
            "border border-[color:var(--g-brand)]/55 bg-[color:var(--g-brand-soft)]/40 ring-2 ring-[color:var(--g-brand)]/30"),
        className,
      )}
    >
      {label}
      {children}
    </div>
  )
}

export function DepartmentLaneHeader({
  department,
  count,
}: {
  department: AgentDepartmentId
  count: number
}) {
  const accent = DEPARTMENT_ACCENT[department]
  return (
    <div className="flex items-baseline gap-2 border-b border-divide pb-2">
      <h3 className={cn("text-xs font-semibold uppercase tracking-wide", accent.accentClass)}>
        {accent.label}
      </h3>
      <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">{count}</span>
      <span className="ml-auto text-[10px] text-[color:var(--g-text-muted)]">Drop agents here</span>
    </div>
  )
}
