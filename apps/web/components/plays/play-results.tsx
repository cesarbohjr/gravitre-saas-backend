"use client"

import Link from "next/link"
import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { fetcher } from "@/lib/fetcher"
import { CheckCircle2, Clock3, ExternalLink, XCircle } from "lucide-react"

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
type Response = { outcomes: Outcome[]; truthRule: string }

function statusIcon(state: string) {
  if (state === "VERIFIED SUCCESS") return <CheckCircle2 className="size-4 text-success" />
  if (state === "VERIFIED FAILURE") return <XCircle className="size-4 text-destructive" />
  return <Clock3 className="size-4 text-muted-foreground" />
}

export function PlayResults({ playKey }: { playKey: string }) {
  const { data } = useSWR<Response>(`/api/plays/${playKey}/outcomes`, fetcher, { refreshInterval: 30_000 })
  const rows = data?.outcomes ?? []
  return (
    <section className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]">
      <div>
        <p className="text-xs font-medium tracking-wide text-muted-foreground">Results</p>
        <h2 className="mt-1 text-base font-semibold">Measured business outcomes</h2>
        <p className="mt-1 text-xs text-muted-foreground">A completed action is not counted as business impact until the source of record verifies the result.</p>
      </div>
      {!rows.length ? <p className="mt-4 rounded-lg border border-dashed border-divide p-4 text-sm text-muted-foreground">No measured results yet. When this Play acts, results will remain pending until Gravitre can verify the business outcome.</p> : (
        <div className="mt-4 divide-y divide-divide border-y border-divide">
          {rows.slice(0, 10).map((row) => {
            const meta = row.metadata ?? {}
            const state = meta.verification_state ?? "INCONCLUSIVE"
            return <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="flex min-w-0 items-start gap-2">
                {statusIcon(state)}
                <div>
                  <div className="flex flex-wrap items-center gap-2"><p className="text-sm font-medium">{(meta.metric_key ?? "Business result").replaceAll("_", " ")}</p><Badge variant="outline">{state.toLowerCase().replaceAll("_", " ")}</Badge></div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {state === "VERIFIED SUCCESS" && typeof meta.delta_value === "number" ? `${meta.currency ? `${meta.currency} ` : ""}${meta.delta_value.toLocaleString()} verified change` : "Not included in verified impact totals"}
                  </p>
                </div>
              </div>
              <Button size="sm" variant="ghost" asChild><Link href={`/plays/${playKey}/results/${row.id}`}>Evidence <ExternalLink className="size-3.5" /></Link></Button>
            </div>
          })}
        </div>
      )}
    </section>
  )
}
