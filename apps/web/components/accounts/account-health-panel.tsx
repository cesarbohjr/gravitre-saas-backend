"use client"

import { useState } from "react"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  accountIntelligenceApi,
  isFeatureOff,
  type AccountHealthDimension,
  type AccountHealthStatus,
} from "@/lib/api"
import { CustomerContextOffState } from "@/components/accounts/customer-context-off-state"

const STATUS_LABEL: Record<AccountHealthStatus, string> = {
  at_risk: "At risk",
  watch: "Watch",
  healthy: "Healthy",
  unknown: "Not enough evidence",
}

const STATUS_CLASS: Record<AccountHealthStatus, string> = {
  at_risk: "text-destructive",
  watch: "text-warning",
  healthy: "text-success",
  unknown: "text-muted-foreground",
}

function describeValue(d: AccountHealthDimension): string | null {
  const v = d.value
  if (v == null) return null
  if (typeof v === "number") return d.key === "contact_gap" ? `${v} days` : d.key === "contact_volume" ? `${v}x usual` : String(v)
  if (typeof v === "object" && v !== null && "direction" in v) return `Trend: ${String((v as { direction: unknown }).direction)}`
  if (typeof v === "object") {
    return Object.entries(v as Record<string, number>)
      .map(([status, n]) => `${n} ${status.replaceAll("_", " ")}`)
      .join(", ")
  }
  return null
}

export function AccountHealthDetail({ entityId }: { entityId: string }) {
  const { data, error, isLoading } = useSWR(["account-health", entityId], () => accountIntelligenceApi.health(entityId), {
    revalidateOnFocus: false,
  })
  if (isLoading && !data) return <p role="status" className="py-3 text-sm text-muted-foreground">Loading account…</p>
  if (error || !data) return <p className="py-3 text-sm text-muted-foreground">This account couldn&apos;t load.</p>
  return (
    <div className="space-y-3 py-3">
      <p className="text-xs text-muted-foreground">
        Each signal is judged on its own with the rule shown. There is no single health score.
      </p>
      <ul className="space-y-3">
        {data.dimensions.map((d) => (
          <li key={d.key} className="border-b border-divide pb-3 last:border-b-0">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-sm font-medium text-foreground">{d.label}</span>
              <span className={`text-xs font-medium ${STATUS_CLASS[d.status]}`}>{STATUS_LABEL[d.status]}</span>
            </div>
            {describeValue(d) ? <p className="text-xs text-foreground">{describeValue(d)}</p> : null}
            {d.note ? <p className="text-xs text-muted-foreground">{d.note}</p> : null}
            {d.evidence.length ? (
              <ul className="mt-1 space-y-0.5">
                {d.evidence.map((e) => (
                  <li key={e} className="text-xs text-muted-foreground [overflow-wrap:anywhere]">
                    {e}
                  </li>
                ))}
              </ul>
            ) : null}
            <details className="mt-1">
              <summary className="cursor-pointer text-xs text-muted-foreground">
                How this is judged ({d.kind === "leading" ? "early signal" : "result"})
              </summary>
              <p className="mt-1 text-xs text-muted-foreground">{d.definition}</p>
            </details>
          </li>
        ))}
      </ul>
    </div>
  )
}

const ACCOUNT_HEALTH_SHOWS =
  "what customers are saying and doing, account by account: tone, urgency and churn-risk language in their emails, each with the words quoted."

/**
 * Accounts with recent customer evidence, most at-risk first. While the feature
 * is switched off (404) or has nothing yet, it says so plainly instead of hiding.
 */
export function AccountHealthPanel() {
  const { data, error, isLoading, mutate } = useSWR("account-health-list", () => accountIntelligenceApi.healthList(20), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  const [open, setOpen] = useState<string | null>(null)
  const featureOff = isFeatureOff(error)

  return (
    <section id="account-health" aria-labelledby="account-health-heading" className="scroll-mt-24 space-y-3">
      <div>
        <h2 id="account-health-heading" className="font-sans text-xl font-medium">Account health</h2>
        <p className="text-sm text-muted-foreground">What customers are saying and doing, account by account.</p>
      </div>
      {featureOff ? (
        <CustomerContextOffState
          feature="Account health"
          whatItShows={ACCOUNT_HEALTH_SHOWS}
          reason="notAvailable"
          emptyMessage="No account has enough recent customer messages yet."
        />
      ) : null}
      {isLoading && !data ? <p role="status" className="text-sm text-muted-foreground">Loading accounts…</p> : null}
      {error && !data && !featureOff ? (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          Accounts couldn&apos;t load.
          <Button variant="outline" size="sm" className="min-h-11" onClick={() => void mutate()}>
            Retry
          </Button>
        </div>
      ) : null}
      {data && data.accounts.length === 0 ? (
        <CustomerContextOffState
          feature="Account health"
          whatItShows={ACCOUNT_HEALTH_SHOWS}
          reason="empty"
          emptyMessage="No account has enough recent customer messages yet."
        />
      ) : null}
      <ul className="divide-y divide-divide">
        {data?.accounts.map((a) => {
          const expanded = open === a.entity.id
          return (
            <li key={a.entity.id}>
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : a.entity.id)}
                className="flex min-h-11 w-full flex-wrap items-center justify-between gap-2 py-2 text-left"
              >
                <span className="text-sm font-medium text-foreground">{a.entity.name || "Unnamed account"}</span>
                <span className="flex flex-wrap gap-1">
                  {a.atRisk.map((label) => (
                    <Badge key={label} variant="outline" className="text-destructive">
                      {label}
                    </Badge>
                  ))}
                  {a.watch.map((label) => (
                    <Badge key={label} variant="outline" className="text-warning">
                      {label}
                    </Badge>
                  ))}
                  {!a.atRisk.length && !a.watch.length ? (
                    <Badge variant="outline" className="text-muted-foreground">Nothing flagged</Badge>
                  ) : null}
                </span>
              </button>
              {expanded ? <AccountHealthDetail entityId={a.entity.id} /> : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
