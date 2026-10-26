"use client"

import type { ReactNode } from "react"
import { DepartmentCover, ListingBadge } from "@/components/marketplace/identity/listing-identity"
import { AgentIdentityEditor } from "@/components/gravitre/agent-identity-editor"
import { presentAgentStatus, agentStatusIsLiveWork } from "@/lib/agent-runtime-status"
import { identityDepartmentFor } from "@/lib/listing-identity"
import { cn } from "@/lib/utils"
import type { Agent } from "@/types/api"

const STATUS_DOT: Record<string, string> = {
  Active: "#19C37D",
  Running: "#2B59E0",
  Idle: "#CBCBC3",
  Failed: "#A3333D",
}

/**
 * Agent detail identity (UIRefresh-Main): the department cover, the avatar on
 * a white circle, name with the edit pencil, description, status chips and
 * the page actions.
 */
export function AgentDetailHeader({
  agent,
  actions,
  chips,
  children,
}: {
  agent: Agent
  actions?: ReactNode
  /** Extra chips after the status chip. */
  chips?: ReactNode
  /** Stats strip, below a hairline. */
  children?: ReactNode
}) {
  const dept = identityDepartmentFor(agent.department)
  const status = presentAgentStatus(agent.status)
  const live = agentStatusIsLiveWork(agent.status)
  const dot = STATUS_DOT[status.label] ?? "#CBCBC3"

  return (
    <section
      aria-label={`${agent.name} identity`}
      data-agent-identity=""
      className="overflow-hidden rounded-[14px] border border-[#e4e4df] bg-white text-[#141513] dark:border-[#2a2c29] dark:bg-[#171917] dark:text-[#ededE8]"
    >
      <DepartmentCover department={agent.department} roleLabel={agent.role} className="h-[120px] sm:h-[150px]" />
      <div className="flex flex-col gap-4 px-5 pb-5 sm:flex-row sm:items-end sm:gap-6 sm:px-7">
        <div className="relative -mt-12 shrink-0 self-start sm:-mt-14">
          {agent.avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- agent avatars may be data URLs
            <img
              src={agent.avatarUrl}
              alt=""
              className="size-24 rounded-full border-4 border-white object-cover shadow-[0_2px_8px_rgba(20,21,19,0.1)] dark:border-[#171917]"
            />
          ) : (
            <ListingBadge kind="agent" department={dept} size={96} className="border-4 border-white dark:border-[#171917]" />
          )}
          <span
            aria-hidden
            className={cn("absolute bottom-2 right-2 size-3.5 rounded-full border-2 border-white dark:border-[#171917]", live && "animate-pulse")}
            style={{ background: dot }}
          />
        </div>
        <div className="min-w-0 flex-1 sm:pt-4">
          <div className="flex items-center gap-2">
            <h1 className="min-w-0 truncate text-[28px] font-semibold leading-tight tracking-[-0.02em] sm:text-[32px]">{agent.name}</h1>
            <AgentIdentityEditor agent={agent} trigger="icon" />
          </div>
          <p className="mt-1.5 max-w-[640px] text-[15px] leading-relaxed text-[#55564f] dark:text-[#a3a49c]">
            {agent.description || "No description yet. Add one with the pencil so teammates know what this agent does."}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ddf3e8] px-2.5 py-1 text-[13px] font-semibold text-[#0a6b47] data-[tone=muted]:bg-[#efefea] data-[tone=muted]:text-[#55564f] data-[tone=failed]:bg-[#f8e4e6] data-[tone=failed]:text-[#a3333d] dark:bg-[#143022] dark:text-[#6fd59a]"
              data-tone={status.label === "Failed" ? "failed" : status.label === "Idle" ? "muted" : undefined}
            >
              <span className="size-1.5 rounded-full" style={{ background: dot }} aria-hidden />
              {status.label}
            </span>
            {chips}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2 sm:justify-end sm:self-end">{actions}</div> : null}
      </div>
      {children ? <div className="border-t border-[#efefea] dark:border-[#232522]">{children}</div> : null}
    </section>
  )
}

/** One cell of the stats strip: label, value and a quiet hint under it. */
export function AgentStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0 px-5 py-4 sm:px-7">
      <dt className="text-[13px] text-[#55564f] dark:text-[#a3a49c]">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">{value}</dd>
      {hint ? <dd className="mt-1 text-xs text-[#8a8b85]">{hint}</dd> : null}
    </div>
  )
}
