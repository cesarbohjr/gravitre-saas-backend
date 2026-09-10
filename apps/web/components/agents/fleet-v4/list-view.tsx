"use client"

import type { ReactNode } from "react"
import {
  GravitreTable,
  GravitreTableShell,
  GravitreTd,
  GravitreTh,
} from "@/components/gravitre/nodus-product/table"
import { cn } from "@/lib/utils"
import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { GravitreAgentRow } from "./gravitre-agent-row"
import type { AgentDepartmentId, FleetAgent } from "./types"

export function ListView({
  agents,
  selectedId,
  onSelect,
  onDepartmentChange,
  showEmptyDepartments = true,
  toolbar,
}: {
  agents: FleetAgent[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  onDepartmentChange?: (agentId: string, department: AgentDepartmentId) => void
  /** Department drop rail only when filters are clear (All). */
  showEmptyDepartments?: boolean
  toolbar?: ReactNode
}) {
  const showDropRail = Boolean(onDepartmentChange) && showEmptyDepartments

  return (
    <div className="space-y-3">
      {showDropRail ? (
        <div className="flex flex-wrap gap-2">
          {FLEET_DEPARTMENT_ORDER.map((department) => (
            <DepartmentDropZone
              key={department}
              department={department}
              onDropAgent={onDepartmentChange}
              className="min-h-[3.25rem] min-w-[8.5rem] flex-1 border border-divide bg-white px-2.5 py-2 shadow-[var(--np-shadow)] sm:flex-none"
              highlightClassName="border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]/50 ring-2 ring-[color:var(--g-brand)]/35"
            >
              <p
                className={cn(
                  "text-[10px] font-semibold uppercase tracking-wide",
                  DEPARTMENT_ACCENT[department].accentClass,
                )}
              >
                {DEPARTMENT_ACCENT[department].label}
              </p>
              <p className="mt-0.5 text-[10px] text-[color:var(--g-text-muted)]">Drop here</p>
            </DepartmentDropZone>
          ))}
        </div>
      ) : null}

      <GravitreTableShell
        toolbar={
          toolbar ?? (
            <p className="text-xs text-[color:var(--g-text-muted)]">
              Operational fleet — dense compare for status, tasks, and model.
            </p>
          )
        }
      >
        <GravitreTable>
          <thead>
            <tr>
              <GravitreTh>Agent</GravitreTh>
              <GravitreTh>Department</GravitreTh>
              <GravitreTh>Status</GravitreTh>
              <GravitreTh>Current work</GravitreTh>
              <GravitreTh>Tasks today</GravitreTh>
              <GravitreTh>Success</GravitreTh>
              <GravitreTh>Model</GravitreTh>
              <GravitreTh>Last active</GravitreTh>
              <GravitreTh>
                <span className="sr-only">Actions</span>
              </GravitreTh>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <GravitreAgentRow
                key={agent.id}
                agent={agent}
                selected={selectedId === agent.id}
                onSelect={onSelect}
                onDepartmentChange={onDepartmentChange}
                draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
              />
            ))}
            {agents.length === 0 ? (
              <tr>
                <GravitreTd className="text-[color:var(--g-text-muted)]">
                  No agents match filters.
                </GravitreTd>
              </tr>
            ) : null}
          </tbody>
        </GravitreTable>
      </GravitreTableShell>
    </div>
  )
}
