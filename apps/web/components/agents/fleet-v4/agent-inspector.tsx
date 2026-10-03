"use client"

import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { relativeTime } from "@/lib/agent-job-result"
import { GravitreAgentDepartmentBadge } from "./gravitre-agent-department-badge"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { FleetAgent } from "./types"

export function AgentInspector({
  agent,
  open,
  onOpenChange,
}: {
  agent: FleetAgent | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-md overflow-y-auto">
        {agent ? (
          <>
            <SheetHeader className="space-y-3 text-left">
              <div className="flex items-start gap-3">
                <GravitreAgentIdentity
                  icon={agent.icon}
                  identityColor={agent.identityColor}
                  status={agent.runtimeState}
                  variant="card"
                  size="lg"
                />
                <div className="min-w-0">
                  <SheetTitle className="text-base">{agent.name}</SheetTitle>
                  <p className="text-sm text-[color:var(--g-text-muted)]">{agent.role}</p>
                  <GravitreAgentDepartmentBadge department={agent.department} className="mt-1 block" />
                </div>
              </div>
              <GravitreAgentStatus
                runtimeState={agent.runtimeState}
                configState={agent.configState}
                showConfig
              />
            </SheetHeader>

            <div className="mt-6 space-y-5 text-sm">
              <div className="grid grid-cols-2 gap-2 rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)]/45 p-2.5">
                <Metric label="Tasks today" value={String(agent.tasksToday)} />
                <Metric label="Success" value={agent.successRate != null ? `${agent.successRate}%` : "—"} verified={agent.successRate != null && agent.successRate >= 90} />
              </div>
              <Field label="Current activity" value={agent.currentActivity ?? "Idle"} />
              <Field label="Last action" value={relativeTime(agent.lastActiveLabel)} />
              <Field label="Model" value={agent.model} />
              <Field label="Tools" value={agent.tools.join(", ") || "—"} />
              <Field label="Workflows" value={agent.workflows.join(", ") || "—"} />
              <div className="flex flex-wrap gap-2 border-t border-divide pt-4">
                <Action label="Run" primary />
                <Action label="Train" />
                <Action label="Edit" />
                <Action label="Pause" />
              </div>
              <p className="text-[11px] text-[color:var(--g-text-muted)]">
                Training lives here — not repeated on every fleet card.
              </p>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

function Metric({ label, value, verified = false }: { label: string; value: string; verified?: boolean }) {
  return <div className="rounded-[8px] bg-background px-3 py-2.5"><p className="text-[10px] font-semibold uppercase tracking-[.12em] text-[color:var(--g-text-muted)]">{label}</p><p className="mt-1 flex items-center gap-1.5 text-lg font-semibold tabular-nums text-[color:var(--g-text-primary)]">{verified ? <span className="size-1.5 rounded-full bg-[color:var(--g-emerald)]" aria-label="Verified" /> : null}{value}</p></div>
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-[color:var(--g-text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-[color:var(--g-text-primary)]">{value}</p>
    </div>
  )
}

function Action({ label, primary }: { label: string; primary?: boolean }) {
  return (
    <span
      className={
        primary
          ? "rounded-md bg-foreground px-2.5 py-1 text-xs font-medium text-background"
          : "rounded-md border border-divide px-2.5 py-1 text-xs font-medium text-[color:var(--g-text-muted)]"
      }
    >
      {label}
    </span>
  )
}
