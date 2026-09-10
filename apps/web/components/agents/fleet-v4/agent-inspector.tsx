"use client"

import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
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
              <Field label="Current activity" value={agent.currentActivity ?? "Idle"} />
              <Field label="Last action" value={agent.lastActiveLabel} />
              <Field label="Model" value={agent.model} />
              <Field label="Tasks today" value={String(agent.tasksToday)} />
              <Field
                label="Success rate"
                value={agent.successRate != null ? `${agent.successRate}%` : "—"}
              />
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

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
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
