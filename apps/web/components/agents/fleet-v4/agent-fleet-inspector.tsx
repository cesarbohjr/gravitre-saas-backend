"use client"

import Link from "next/link"
import { Brain, Database, MessageSquare, Pause, Play, RefreshCw, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { StatusChip } from "@/components/gravitre/visual"
import { normalizeAgentStatus, presentAgentStatus } from "@/lib/agent-runtime-status"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

/**
 * Unified Agents 4.0 inspector body — one content model for sheet + desktop panel.
 * Train lives here only (not on every fleet card). No glow/orb customization.
 */

export type AgentFleetInspectorAgent = {
  id: string
  name: string
  role: string
  department: string
  description?: string
  status: string
  model?: string | null
  icon?: string | null
  avatarColor?: string | null
  avatarUrl?: string | null
  personality?: {
    color?: string
    gradient?: string
    glow?: string
  }
  stats: {
    tasksToday: number
    successRate: number | null
    avgResponseTime: string
    workflowsUsing: number
  }
  capabilities?: string[]
  permissions?: string[]
  connectedSystems?: string[]
  lastAction?: string
  lastActionTime?: string
  knowledgeDocCount?: number
}

export function AgentFleetInspectorBody({
  agent,
  layout = "sheet",
  onStart,
  onStop,
  isMutating,
  successRateDisplay,
}: {
  agent: AgentFleetInspectorAgent
  layout?: "sheet" | "panel"
  onStart?: (agent: AgentFleetInspectorAgent) => Promise<void>
  onStop?: (agent: AgentFleetInspectorAgent) => Promise<void>
  isMutating?: boolean
  successRateDisplay: number | null
}) {
  const normalized = normalizeAgentStatus(agent.status)
  const status = presentAgentStatus(normalized)
  const systems =
    (agent.connectedSystems?.length ? agent.connectedSystems : agent.permissions) ?? []
  const dense = layout === "sheet"

  return (
    <div className="flex h-full flex-col">
      <div className={cn("border-b border-border", dense ? "px-5 py-5" : "p-6")}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <AgentIdentityAvatar agent={agent} size={dense ? "md" : "lg"} showStatusDot />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className={cn(TYPE.sectionTitle, "truncate")}>{agent.name}</h2>
                <span className={cn("rounded-full bg-secondary px-2 py-0.5", TYPE.metricLabel)}>
                  {agent.department}
                </span>
                <StatusChip status={normalized} pulse={status.pulse}>
                  {status.label}
                </StatusChip>
              </div>
              <p className="text-sm text-muted-foreground">{agent.role}</p>
            </div>
          </div>
          {!dense ? (
            <div className="flex shrink-0 items-center gap-2">
              {agent.status === "active" ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => void onStop?.(agent)}
                  disabled={isMutating}
                >
                  <Pause className="h-3.5 w-3.5" />
                  Pause
                </Button>
              ) : agent.status !== "error" ? (
                <Button
                  size="sm"
                  className="gap-2"
                  onClick={() => void onStart?.(agent)}
                  disabled={isMutating}
                >
                  <Play className="h-3.5 w-3.5" />
                  Activate
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  size="sm"
                  className="gap-2"
                  onClick={() => void onStart?.(agent)}
                  disabled={isMutating}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Retry
                </Button>
              )}
              <Button variant="ghost" size="icon" asChild aria-label={`Configure ${agent.name}`}>
                <Link href={`/agents/${agent.id}`}>
                  <Settings className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          ) : null}
        </div>

        {agent.description ? (
          <p className="mt-3 text-sm text-muted-foreground">{agent.description}</p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "rounded-md px-2 py-1 text-xs font-medium",
              successRateDisplay != null
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "bg-secondary text-muted-foreground",
            )}
          >
            {successRateDisplay != null ? `${successRateDisplay}% success` : "No tasks yet"}
          </span>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs text-muted-foreground">
            {agent.stats.tasksToday} tasks
          </span>
          {agent.model ? (
            <span className="max-w-[140px] truncate rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {agent.model}
            </span>
          ) : null}
          {(agent.knowledgeDocCount ?? 0) > 0 ? (
            <span className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {agent.knowledgeDocCount} training docs
            </span>
          ) : null}
        </div>
      </div>

      <div className={cn("grid grid-cols-3 gap-px bg-divide", !dense && "sm:grid-cols-4")}>
        <StatCell label="Tasks" value={String(agent.stats.tasksToday)} />
        <StatCell
          label="Success"
          value={successRateDisplay != null ? `${successRateDisplay}%` : "—"}
        />
        <StatCell label="Flows" value={String(agent.stats.workflowsUsing)} />
        {!dense ? <StatCell label="Avg" value={agent.stats.avgResponseTime} /> : null}
      </div>

      <div className={cn("flex-1 space-y-5", dense ? "px-5 py-4" : "p-6")}>
        {agent.capabilities && agent.capabilities.length > 0 ? (
          <section>
            <h3 className={cn(TYPE.eyebrow, "mb-2 block")}>Capabilities</h3>
            <div className="flex flex-wrap gap-2">
              {agent.capabilities.map((cap) => (
                <span
                  key={cap}
                  className="rounded-md border border-divide bg-[color:var(--g-surface-2)] px-2.5 py-1 text-xs text-foreground"
                >
                  {cap}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        {systems.length > 0 ? (
          <section>
            <h3 className={cn(TYPE.eyebrow, "mb-2 block")}>Connected systems</h3>
            <div className="flex flex-wrap gap-2">
              {systems.map((sys) => (
                <span
                  key={sys}
                  className="rounded-md border border-info/20 bg-info/10 px-2.5 py-1 text-xs text-info"
                >
                  {sys}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        <section>
          <h3 className={cn(TYPE.eyebrow, "mb-2 block")}>Recent activity</h3>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <p className="text-sm text-foreground">{agent.lastAction || "No activity yet"}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {agent.lastActionTime || "unknown"}
            </p>
          </div>
        </section>
      </div>

      <div
        className={cn(
          "space-y-3 border-t border-border bg-secondary/30",
          dense ? "px-5 py-4" : "p-6",
        )}
      >
        <div className={cn("grid gap-2", dense ? "grid-cols-1" : "grid-cols-3")}>
          {dense ? (
            <Button variant="outline" className="w-full gap-1.5" asChild>
              <Link href={`/agents/${agent.id}/chat`}>
                <MessageSquare className="h-3.5 w-3.5" />
                Chat
              </Link>
            </Button>
          ) : null}
          <Button variant="outline" size="sm" className="gap-1.5" asChild>
            <Link href={`/agents/${agent.id}?tab=training`}>
              <Brain className="h-3.5 w-3.5" />
              Train
            </Link>
          </Button>
          <Button variant={dense ? "default" : "outline"} size="sm" className="gap-1.5" asChild>
            <Link href={`/lite/assign?agent=${agent.id}`}>
              <Play className="h-3.5 w-3.5" />
              Assign
            </Link>
          </Button>
          {!dense ? (
            <Button variant="outline" size="sm" className="gap-1.5" asChild>
              <Link href={`/agents/${agent.id}/memory`}>
                <Database className="h-3.5 w-3.5" />
                Memory
              </Link>
            </Button>
          ) : null}
        </div>
        <Button variant="outline" className="w-full justify-between" asChild>
          <Link href={`/agents/${agent.id}`}>
            View / edit profile
            <span className="text-muted-foreground">Appearance · settings</span>
          </Link>
        </Button>
        <p className="text-[11px] text-muted-foreground">
          Training and appearance live in profile/inspector — not on every fleet card. Appearance
          uses soft tiles only (no glow orbs).
        </p>
      </div>
    </div>
  )
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[color:var(--g-surface-1)] p-3 text-center sm:p-4">
      <div className="text-lg font-semibold text-foreground sm:text-xl">{value}</div>
      <div className={TYPE.metricLabel}>{label}</div>
    </div>
  )
}
