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
    <section aria-labelledby="dashboard-attention" className={cn("space-y-2", className)}>
      <h2 id="dashboard-attention" className="text-sm font-semibold text-foreground">
        Needs your attention
      </h2>
      {items.length === 0 ? (
        <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <CheckCircle2 className="size-4 text-[color:var(--g-brand)]" aria-hidden />
          Nothing needs you right now.
        </p>
      ) : (
        <ul className="divide-y divide-[color:var(--g-border-subtle)] rounded-[var(--np-radius-lg)] border border-[color:var(--g-border-default)] bg-card">
          {items.map((item) => {
            const Icon = TONE_ICON[item.tone]
            return (
              <li key={item.id}>
                <Link
                  href={item.href}
                  className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                >
                  <Icon className={cn("mt-0.5 size-4 shrink-0", TONE_CLASS[item.tone])} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium text-foreground">{item.title}</span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {item.detail}
                    </span>
                  </span>
                  <ArrowRight
                    className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
