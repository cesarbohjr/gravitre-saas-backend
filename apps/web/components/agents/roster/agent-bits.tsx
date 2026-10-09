"use client"

import Link from "next/link"
import type { RosterAgent } from "@/lib/agents-roster"
import { DEPARTMENT_ICONS } from "@/lib/department-icons"
import { cn } from "@/lib/utils"

export function giveTaskHref(agentId: string): string {
  return `/assignments/new?agent=${encodeURIComponent(agentId)}`
}

export function agentHref(agentId: string): string {
  return `/agents/${encodeURIComponent(agentId)}`
}

export function newAgentHref(departmentLabel?: string): string {
  return departmentLabel ? `/agents/new?department=${encodeURIComponent(departmentLabel)}` : "/agents/new"
}

/** Department icon tile in the department tint, with a live / blocked / not-set-up dot. */
export function AgentAvatar({
  agent,
  size = "lg",
  dot = true,
  className,
}: {
  agent: Pick<RosterAgent, "department" | "state">
  size?: "lg" | "sm"
  dot?: boolean
  className?: string
}) {
  const Icon = DEPARTMENT_ICONS[agent.department] ?? DEPARTMENT_ICONS.general
  const dotClass =
    agent.state === "blocked" ? "amber" : agent.state === "not_set_up" ? "grey" : agent.state === "working" ? "live" : ""
  return (
    <span className={cn("gv-ava rs-ava", size === "lg" && "lg", `rs-d-${agent.department}`, className)} aria-hidden>
      <Icon size={size === "lg" ? 22 : 17} strokeWidth={1.9} aria-hidden />
      {dot ? <span className={cn("dot", dotClass)} /> : null}
    </span>
  )
}

export function AppChips({ apps, max = 4 }: { apps: string[]; max?: number }) {
  if (apps.length === 0) return null
  const shown = apps.slice(0, max)
  return (
    <div className="rs-apps">
      {shown.map((app) => (
        <span key={app} className="gv-app">
          {app}
        </span>
      ))}
      {apps.length > max ? <span className="gv-app">+{apps.length - max}</span> : null}
    </div>
  )
}

export function GiveTaskLink({ agent, className }: { agent: Pick<RosterAgent, "id" | "name">; className?: string }) {
  return (
    <Link
      className={cn("gv-btn ghost sm", className)}
      href={giveTaskHref(agent.id)}
      aria-label={`Give ${agent.name} a task`}
    >
      Give a task
    </Link>
  )
}

export function WarnIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
      <path d="M12 3 2 20h20z" />
      <path d="M12 10v4M12 17h.01" />
    </svg>
  )
}
