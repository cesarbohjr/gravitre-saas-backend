"use client"

import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { fetcher } from "@/lib/fetcher"
import { cn } from "@/lib/utils"
import { ArrowRight, CheckCircle2, Clock3, ExternalLink, XCircle } from "lucide-react"

type Outcome = {
  id: string
  measurement_status?: string
  before_value?: number | null
  after_value?: number | null
  measured_at?: string | null
  created_at?: string
  metadata?: {
    verification_state?: string
    metric_key?: string
    delta_value?: number | null
    unit?: string
    currency?: string
    verified?: boolean
  }
}
export type PlayOutcomesResponse = { outcomes: Outcome[]; truthRule: string }

const STATE_STYLE: Record<string, { rail: string; pill: string }> = {
  "VERIFIED SUCCESS": {
    rail: "bg-[color:var(--g-emerald)]",
    pill: "bg-[color:var(--g-emerald-pale)] text-[color:var(--g-brand-active)] dark:bg-[color:var(--g-emerald-soft)] dark:text-[color:var(--g-brand)]",
  },
  "VERIFIED FAILURE": { rail: "bg-destructive", pill: "bg-destructive/10 text-destructive" },
}
const PENDING_STYLE = { rail: "bg-[color:var(--g-approval)]", pill: "bg-[color:var(--g-approval)]/12 text-[color:var(--g-approval)]" }

function statusIcon(state: string) {
  if (state === "VERIFIED SUCCESS") return <CheckCircle2 className="size-4 text-[color:var(--g-emerald)]" />
  if (state === "VERIFIED FAILURE") return <XCircle className="size-4 text-destructive" />
  return <Clock3 className="size-4 text-[color:var(--g-approval)]" />
}

function when(iso?: string | null): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function PlayResults({ playKey }: { playKey: string }) {
  const { data } = useSWR<PlayOutcomesResponse>(`/api/plays/${playKey}/outcomes`, fetcher, { refreshInterval: 30_000 })
  const rows = data?.outcomes ?? []
  return (
    <section className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)]">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-divide p-4">
        <div>
          <h2 className="text-[15px] font-semibold text-foreground">Results</h2>
          <p className="mt-1 max-w-xl text-xs leading-5 text-muted-foreground">A completed action is not counted as business impact until the source of record verifies the result.</p>
        </div>
        <Button size="sm" variant="ghost" className="min-h-9 text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]" asChild>
          <Link href="/activity">View all activity <ArrowRight className="size-3.5" /></Link>
        </Button>
      </div>
      {!rows.length ? <p className="m-4 rounded-lg border border-dashed border-divide p-4 text-sm text-muted-foreground">No measured results yet. When this Play acts, results will remain pending until Gravitre can verify the business outcome.</p> : (
        <ul className="divide-y divide-divide">
          {rows.slice(0, 10).map((row) => {
            const meta = row.metadata ?? {}
            const state = meta.verification_state ?? "INCONCLUSIVE"
            const style = STATE_STYLE[state] ?? PENDING_STYLE
            const at = when(row.measured_at ?? row.created_at)
            return <li key={row.id} className="relative flex flex-wrap items-center justify-between gap-3 py-3 pl-5 pr-3">
              <span aria-hidden className={cn("absolute inset-y-2 left-2 w-[3px] rounded-full", style.rail)} />
              <div className="flex min-w-0 items-start gap-2.5">
                <span className="mt-0.5">{statusIcon(state)}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium capitalize text-foreground">{(meta.metric_key ?? "Business result").replaceAll("_", " ")}</p>
                    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium capitalize", style.pill)}>{state.toLowerCase().replaceAll("_", " ")}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {state === "VERIFIED SUCCESS" && typeof meta.delta_value === "number" ? `${meta.currency ? `${meta.currency} ` : ""}${meta.delta_value.toLocaleString()} verified change` : "Not included in verified impact totals"}
                    {at ? ` · ${at}` : ""}
                  </p>
                </div>
              </div>
              <Button size="sm" variant="ghost" asChild><Link href={`/plays/${playKey}/results/${row.id}`}>Evidence <ExternalLink className="size-3.5" /></Link></Button>
            </li>
          })}
        </ul>
      )}
    </section>
  )
}
