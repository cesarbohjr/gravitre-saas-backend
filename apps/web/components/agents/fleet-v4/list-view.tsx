"use client"

import type { ReactNode } from "react"
import {
  GravitreTable,
  GravitreTableShell,
  GravitreTd,
  GravitreTh,
} from "@/components/gravitre/nodus-product/table"
import { GravitreAgentRow } from "./gravitre-agent-row"
import type { FleetAgent } from "./types"

export function ListView({
  agents,
  selectedId,
  onSelect,
  toolbar,
}: {
  agents: FleetAgent[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  toolbar?: ReactNode
}) {
  return (
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
            />
          ))}
          {agents.length === 0 ? (
            <tr>
              <GravitreTd className="text-[color:var(--g-text-muted)]">No agents match filters.</GravitreTd>
            </tr>
          ) : null}
        </tbody>
      </GravitreTable>
    </GravitreTableShell>
  )
}
