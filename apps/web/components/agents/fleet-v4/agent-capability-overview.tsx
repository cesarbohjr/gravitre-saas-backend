"use client"

import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { FleetAgent } from "./types"

function agentScopeLabel(departmentLabel: string, role: string): string {
  const parts = [departmentLabel, role].map((part) => part.trim()).filter(Boolean)
  return parts.filter((part, index) => parts.findIndex((other) => other.toLowerCase() === part.toLowerCase()) === index).join(" / ")
}

function reportedModel(model: string): string {
  const text = model.trim()
  return !text || /^[—–-]+$/.test(text) ? "Not reported" : text
}

/** Figma 10:73 + 10:78, adapted to the real filtered roster and saved identity. */
export function AgentCapabilityOverview({ agent, connectedSystems = [], onInspect }: { agent: FleetAgent; connectedSystems?: string[]; onInspect: (id: string) => void }) {
  const systems = connectedSystems
  const scope = agentScopeLabel(agent.departmentLabel, agent.role)
  return (
    <section
      aria-label={`${agent.name} overview`}
      className="mb-5 flex flex-col gap-4 rounded-xl border border-border bg-[color:var(--g-surface-1)] p-4"
      data-testid="agent-capability-overview"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <GravitreAgentIdentity icon={agent.icon} identityColor={agent.identityColor} size="md" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h2 className="min-w-0 truncate font-sans text-base font-semibold leading-snug">{agent.name}</h2>
            <GravitreAgentStatus runtimeState={agent.runtimeState} configState={agent.configState} />
          </div>
          {scope ? <p className="truncate text-sm text-muted-foreground">{scope}</p> : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button onClick={() => onInspect(agent.id)} className="min-h-11 flex-1 sm:flex-none">
          Inspect agent <ArrowRight className="ml-2 size-4" aria-hidden />
        </Button>
        <Button asChild variant="ghost" className="min-h-11 flex-1 text-muted-foreground hover:text-foreground sm:flex-none">
          <Link href={`/agents/${encodeURIComponent(agent.id)}`}>Configure</Link>
        </Button>
      </div>
      </div>

      <dl className="grid min-w-0 grid-cols-2 gap-x-6 gap-y-3 border-t border-border pt-3 text-sm sm:grid-cols-3">
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">Model</dt>
          <dd className="mt-0.5 truncate">{reportedModel(agent.model)}</dd>
        </div>
        <div className="col-span-2 min-w-0 sm:col-span-1">
          <dt className="text-xs text-muted-foreground">Connected systems</dt>
          <dd className="mt-0.5 truncate" title={systems.join(" · ") || undefined}>{systems.length ? systems.join(" · ") : "No systems listed"}</dd>
        </div>
        {agent.workflowCount != null ? (
          <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">Used in workflows</dt>
            <dd className="mt-0.5 tabular-nums">{agent.workflowCount}</dd>
          </div>
        ) : null}
        {agent.currentActivity ? (
          <p className="col-span-full truncate text-sm text-[color:var(--g-emerald-mint)]">{agent.currentActivity}</p>
        ) : null}
      </dl>
    </section>
  )
}
