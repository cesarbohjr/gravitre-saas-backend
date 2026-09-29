"use client"

import Link from "next/link"
import { AlertTriangle, ArrowRight, CheckCircle2, ShieldCheck, TrendingDown } from "lucide-react"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"

type AttentionItem = {
  id: string
  tone: "approval" | "error" | "risk"
  title: string
  detail: string
  href: string
}

const TONE_ICON = {
  approval: ShieldCheck,
  error: AlertTriangle,
  risk: TrendingDown,
} as const

const TONE_CLASS = {
  approval: "text-[color:var(--g-signal)]",
  error: "text-destructive",
  risk: "text-warning",
} as const

const TONE_BAR = {
  approval: "before:bg-[color:var(--g-signal)]",
  error: "before:bg-destructive",
  risk: "before:bg-warning",
} as const

const TONE_ACTION = {
  approval: "Review",
  error: "Open team",
  risk: "Investigate",
} as const

/** Attention-first lead for the Dashboard. Only items backed by loaded data are listed. */
export function buildAttentionItems(data: HomeDashboardData): AttentionItem[] {
  const items: AttentionItem[] = []
  if (data.pendingApprovals > 0) {
    const first = data.pendingApprovalItems.find((item) => item.title)?.title
    items.push({
      id: "approvals",
      tone: "approval",
      title: `${data.pendingApprovals} approval${data.pendingApprovals === 1 ? "" : "s"} waiting on you`,
      detail: first ? first : "Review before agents continue.",
      href: APP_ROUTES.approvals,
    })
  }
  const errored = data.agentStatusCounts?.error ?? 0
  if (errored > 0) {
    items.push({
      id: "agent-errors",
      tone: "error",
      title: `${errored} agent${errored === 1 ? " needs" : "s need"} attention`,
      detail: "Stopped with an error. Open the team to retry or reassign.",
      href: "/agents",
    })
  }
  for (const risk of data.revenueRisks.slice(0, 2)) {
    items.push({
      id: `risk-${risk.id}`,
      tone: "risk",
      title: risk.title,
      detail: risk.summary,
      href: APP_ROUTES.revenueRisk,
    })
  }
  return items
}

export function AttentionStrip({ data, className }: { data: HomeDashboardData; className?: string }) {
  const items = buildAttentionItems(data)

  return (
    <section aria-labelledby="dashboard-attention" className={cn("space-y-2.5", className)}>
      <div className="flex items-baseline gap-2">
        <h2 id="dashboard-attention" className="text-[15px] font-semibold tracking-[-0.01em] text-foreground">
          Needs your attention
        </h2>
        {items.length > 0 ? (
          <span className="text-[13px] font-semibold tabular-nums text-[color:var(--g-signal)]">
            {items.length}
          </span>
        ) : null}
      </div>
      {items.length === 0 ? (
        <div className="flex items-center gap-3 border-y border-[color:var(--g-border-subtle)] px-1 py-4">
          <span className="flex size-8 shrink-0 items-center justify-center">
            <CheckCircle2 className="size-4 text-[color:var(--g-brand)]" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-[13px] font-medium text-foreground">Nothing needs you right now.</span>
            <span className="block text-xs text-muted-foreground">
              Approvals, agent errors and revenue signals surface here as they happen.
            </span>
          </span>
        </div>
      ) : (
        <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-default)]">
          {items.map((item) => {
            const Icon = TONE_ICON[item.tone]
            return (
              <li key={item.id}>
                <Link
                  href={item.href}
                  className={cn(
                    "group relative flex items-center gap-3 overflow-hidden py-3 pl-5 pr-2 transition-colors hover:bg-[color:var(--g-background-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                    "before:absolute before:inset-y-2 before:left-0 before:w-[2px]",
                    TONE_BAR[item.tone],
                  )}
                >
                  <Icon className={cn("size-[18px] shrink-0", TONE_CLASS[item.tone])} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[14px] font-medium text-foreground">{item.title}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {item.detail}
                    </span>
                  </span>
                  <span className="hidden shrink-0 items-center gap-1 rounded-[var(--np-radius-sm)] border border-[color:var(--g-border-default)] px-2.5 py-1 text-xs font-medium text-foreground transition-colors group-hover:bg-[color:var(--g-surface-1)] sm:inline-flex">
                    {TONE_ACTION[item.tone]}
                    <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
                  </span>
                  <ArrowRight className="size-4 shrink-0 text-muted-foreground sm:hidden" aria-hidden />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
