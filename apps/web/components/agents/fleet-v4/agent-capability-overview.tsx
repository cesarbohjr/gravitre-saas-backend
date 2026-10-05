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
  return (
    <section aria-label={`${agent.name} overview`} className="mb-5 grid overflow-hidden rounded-xl md:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]" data-testid="agent-capability-overview">
      <div className="flex min-w-0 flex-col items-start bg-[color:var(--g-emerald-deep)] p-5 text-white sm:p-6">
        <p className="text-xs font-semibold text-[color:var(--g-emerald-mint)]">{agentScopeLabel(agent.departmentLabel, agent.role)}</p>
        <div className="mt-4 flex items-center gap-3">
          <GravitreAgentIdentity icon={agent.icon} identityColor={agent.identityColor} size="md" />
          <h2 className="min-w-0 break-words font-sans text-[29px] font-medium leading-tight">{agent.name}</h2>
        </div>
        <div className="mt-3 rounded-md bg-white px-2 py-1"><GravitreAgentStatus runtimeState={agent.runtimeState} configState={agent.configState} /></div>
        {agent.currentActivity ? <p className="mt-3 text-sm leading-6 text-[color:var(--g-emerald-mint)]">{agent.currentActivity}</p> : null}
        <Button onClick={() => onInspect(agent.id)} className="mt-5 min-h-11 bg-white text-[color:var(--g-emerald-deep)] hover:bg-[color:var(--g-emerald-mint)] focus-visible:ring-white">Inspect agent <ArrowRight className="ml-2 size-4" aria-hidden /></Button>
      </div>
      <div className="min-w-0 bg-[color:var(--g-surface-1)] p-5 sm:p-6">
        <h3 className="text-xs font-semibold text-[color:var(--g-emerald-deep)]">Capability context</h3>
        <dl className="mt-4 space-y-3 text-sm">
          <div><dt className="text-xs text-muted-foreground">Model</dt><dd className="mt-1 break-words">{reportedModel(agent.model)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Connected systems</dt><dd className="mt-1 break-words">{systems.length ? systems.join(" · ") : "No systems listed"}</dd></div>
          {agent.workflowCount != null ? <div><dt className="text-xs text-muted-foreground">Used in workflows</dt><dd className="mt-1 tabular-nums">{agent.workflowCount}</dd></div> : null}
        </dl>
        <Button asChild variant="ghost" size="sm" className="mt-4 -ml-3 text-[color:var(--g-emerald-deep)]"><Link href={`/agents/${encodeURIComponent(agent.id)}`}>Open configuration <ArrowRight className="ml-2 size-3.5" aria-hidden /></Link></Button>
      </div>
    </section>
  )
}
