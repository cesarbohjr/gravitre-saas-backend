"use client"

import Link from "next/link"
import {
  ArrowUpRight,
  Database,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  Settings,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusChip } from "@/components/gravitre/visual"
import { NucleoHistory } from "@/components/icons/nucleo/semantic"
import { LEGACY_COLOR_TO_IDENTITY, LEGACY_ICON_TO_ROLE } from "@/lib/agent-identity-bridge"
import { isAgentAvatarColorId, isAgentIconId } from "@/lib/agent-identity"
import { AGENT_DEPARTMENT_OPTIONS, normalizeAgentDepartment, type AgentDepartment } from "@/lib/agent-display"
import { relativeTime } from "@/lib/agent-job-result"
import { normalizeAgentStatus, presentAgentStatus } from "@/lib/agent-runtime-status"
import { cn } from "@/lib/utils"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { IDENTITY_COLOR_TOKENS, ROLE_ICON_REGISTRY, suggestRoleIcon } from "./identity-tokens"
import type { AgentIdentityColorId, AgentRoleIconId } from "./types"

function inspectorRoleIcon(agent: AgentFleetInspectorAgent): AgentRoleIconId {
  if (agent.icon && agent.icon in ROLE_ICON_REGISTRY) return agent.icon as AgentRoleIconId
  if (agent.icon && isAgentIconId(agent.icon)) return LEGACY_ICON_TO_ROLE[agent.icon]
  return suggestRoleIcon(agent.role, agent.name, agent.department)
}

function inspectorIdentityColor(agent: AgentFleetInspectorAgent): AgentIdentityColorId {
  const color = agent.avatarColor
  if (color && color in IDENTITY_COLOR_TOKENS) return color as AgentIdentityColorId
  if (color && isAgentAvatarColorId(color)) return LEGACY_COLOR_TO_IDENTITY[color]
  return "violet"
}

/**
 * Unified Agents inspector body — one content model for sheet + desktop panel.
 * Train lives here only (not on every fleet card).
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
  onDepartmentChange,
  onClose,
  isMutating,
  successRateDisplay,
}: {
  agent: AgentFleetInspectorAgent
  layout?: "sheet" | "panel"
  onClose?: () => void
  onStart?: (agent: AgentFleetInspectorAgent) => Promise<void>
  onStop?: (agent: AgentFleetInspectorAgent) => Promise<void>
  onDepartmentChange?: (agentId: string, department: AgentDepartment) => void
  isMutating?: boolean
  successRateDisplay: number | null
}) {
  const normalized = normalizeAgentStatus(agent.status)
  const status = presentAgentStatus(normalized)
  const systems =
    (agent.connectedSystems?.length ? agent.connectedSystems : agent.permissions) ?? []
  const departmentValue = (() => {
    const normalizedDept = normalizeAgentDepartment(agent.department)
    if (AGENT_DEPARTMENT_OPTIONS.includes(normalizedDept)) return normalizedDept
    if (normalizedDept === "Support") return "Customer Success"
    if (normalizedDept === "HR") return "General"
    return "Operations"
  })()
  const avg = agent.stats.avgResponseTime
  const showAvg = Boolean(avg) && avg !== "—" && avg !== "-"

  return (
    <div className="flex h-full flex-col" data-inspector-layout={layout}>
      <div className="px-5 pt-5 pb-4">
        <div className={cn("flex items-start gap-3", layout === "sheet" && "pr-8")}>
          <GravitreAgentIdentity
            icon={inspectorRoleIcon(agent)}
            identityColor={inspectorIdentityColor(agent)}
            size="md"
          />
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-base font-semibold leading-tight tracking-tight text-foreground">
              {agent.name}
            </h2>
            <p className="mt-0.5 truncate text-[13px] text-muted-foreground">{agent.role}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            asChild
            aria-label={`Open ${agent.name} settings`}
            className="shrink-0"
          >
            <Link href={`/agents/${agent.id}`}>
              <Settings className="size-4" />
            </Link>
          </Button>
          {onClose ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onClose}
              aria-label="Close agent details"
              className="-mr-1 shrink-0"
            >
              <X className="size-4" />
            </Button>
          ) : null}
        </div>

        {agent.description ? (
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            {agent.description}
          </p>
        ) : null}

        <div className="mt-4 flex items-center gap-2">
          <Button size="sm" className="flex-1" asChild>
            <Link href={`/lite/assign?agent=${agent.id}`}>
              <Play className="size-3.5" />
              Assign work
            </Link>
          </Button>
          <Button variant="outline" size="sm" className="flex-1" asChild>
            <Link href={`/agents/${agent.id}/chat`}>
              <MessageSquare className="size-3.5" />
              Chat
            </Link>
          </Button>
          {agent.status === "active" ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void onStop?.(agent)}
              disabled={isMutating}
            >
              <Pause className="size-3.5" />
              Pause
            </Button>
          ) : agent.status !== "error" ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void onStart?.(agent)}
              disabled={isMutating}
            >
              <Play className="size-3.5" />
              Activate
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => void onStart?.(agent)}
              disabled={isMutating}
            >
              <RefreshCw className="size-3.5" />
              Retry
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 divide-y divide-[color:var(--g-border-subtle)] border-t border-[color:var(--g-border-subtle)]">
        <section className="px-5 py-4">
          <dl className="grid grid-cols-[minmax(104px,auto)_1fr] items-center gap-x-4 gap-y-2.5 text-[13px]">
            <dt className="text-muted-foreground">Status</dt>
            <dd>
              <StatusChip status={normalized} pulse={status.pulse} appearance="plain">
                {status.label}
              </StatusChip>
            </dd>
            <dt className="text-muted-foreground">Department</dt>
            <dd>
              {onDepartmentChange ? (
                <select
                  aria-label={`Department for ${agent.name}`}
                  value={departmentValue}
                  disabled={isMutating}
                  onChange={(event) => {
                    onDepartmentChange(agent.id, event.target.value as AgentDepartment)
                  }}
                  className="h-7 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-background px-2 text-[13px] text-foreground hover:border-[color:var(--g-border-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {AGENT_DEPARTMENT_OPTIONS.map((dept) => (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-foreground">{agent.department}</span>
              )}
            </dd>
            {agent.model ? (
              <>
                <dt className="text-muted-foreground">Model</dt>
                <dd className="truncate text-foreground">{agent.model}</dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">Tasks today</dt>
            <dd className="tabular-nums text-foreground">{agent.stats.tasksToday}</dd>
            <dt className="text-muted-foreground">Success rate</dt>
            <dd className="tabular-nums text-foreground">
              {successRateDisplay != null ? (
                `${successRateDisplay}%`
              ) : (
                <span className="text-muted-foreground">No completed tasks yet</span>
              )}
            </dd>
            <dt className="text-muted-foreground">Workflows</dt>
            <dd className="tabular-nums text-foreground">{agent.stats.workflowsUsing}</dd>
            {showAvg ? (
              <>
                <dt className="text-muted-foreground">Avg response</dt>
                <dd className="tabular-nums text-foreground">{avg}</dd>
              </>
            ) : null}
            {(agent.knowledgeDocCount ?? 0) > 0 ? (
              <>
                <dt className="text-muted-foreground">Training docs</dt>
                <dd className="tabular-nums text-foreground">{agent.knowledgeDocCount}</dd>
              </>
            ) : null}
          </dl>
        </section>

        {agent.capabilities && agent.capabilities.length > 0 ? (
          <section className="px-5 py-4">
            <h3 className="mb-2 text-xs font-medium text-muted-foreground">Capabilities</h3>
            <div className="flex flex-wrap gap-1.5">
              {agent.capabilities.map((cap) => (
                <Badge key={cap} variant="secondary">
                  {cap}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        {systems.length > 0 ? (
          <section className="px-5 py-4">
            <h3 className="mb-2 text-xs font-medium text-muted-foreground">Connected systems</h3>
            <div className="flex flex-wrap gap-1.5">
              {systems.map((sys) => (
                <Badge key={sys} variant="outline">
                  {sys}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        <section className="px-5 py-4">
          <h3 className="mb-2 text-xs font-medium text-muted-foreground">Recent activity</h3>
          <p className="text-[13px] text-foreground">{agent.lastAction || "No activity yet"}</p>
          {agent.lastActionTime ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{relativeTime(agent.lastActionTime)}</p>
          ) : null}
        </section>
      </div>

      <nav
        aria-label={`More for ${agent.name}`}
        className="grid grid-cols-2 gap-1 border-t border-[color:var(--g-border-subtle)] px-3 py-3"
      >
        <InspectorLink href={`/agents/${agent.id}?tab=training`} icon={<NucleoHistory className="size-3.5" />}>
          Train
        </InspectorLink>
        <InspectorLink href={`/agents/${agent.id}/memory`} icon={<Database className="size-3.5" />}>
          Memory
        </InspectorLink>
        <InspectorLink
          href={`/agents/${agent.id}`}
          icon={<ArrowUpRight className="size-3.5" />}
          className="col-span-2"
        >
          Open full profile
        </InspectorLink>
      </nav>
    </div>
  )
}

function InspectorLink({
  href,
  icon,
  children,
  className,
}: {
  href: string
  icon: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <Button variant="ghost" size="sm" className={cn("justify-start text-foreground/80", className)} asChild>
      <Link href={href}>
        {icon}
        {children}
      </Link>
    </Button>
  )
}
