"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/fetcher"
import { cn } from "@/lib/utils"
import { ArrowLeft, ArrowRight, CircleAlert, PlayCircle, Workflow } from "lucide-react"
import { PlaySetup } from "@/components/plays/play-setup"
import { PlayRunControl } from "@/components/plays/play-run-control"
import { PlayResults, type PlayOutcomesResponse } from "@/components/plays/play-results"
import { AuthorityLadder, earnedRungs } from "@/components/plays/authority-ladder"

type Readiness = {
  observe_ready?: boolean
  recommend_ready?: boolean
  act_with_approval_ready?: boolean
  act_within_policy_ready?: boolean
  blockers?: string[]
  connector_groups?: Array<Record<string, unknown>>
  actions?: Array<Record<string, unknown>>
  signals?: Array<Record<string, unknown>>
}
type Payload = {
  play: { key: string; name: string; objective: string; version: string }
  readiness: Readiness
  workflowBindings: Array<Record<string, unknown>>
  workflowBindingCount: number
}

function mode(readiness: Readiness): string {
  if (readiness.act_with_approval_ready) return "Act with approval"
  if (readiness.recommend_ready) return "Recommend"
  if (readiness.observe_ready) return "Observe"
  return "Setup required"
}

/**
 * The operating path, with each stage tied to the authority rung that unlocks it.
 * Measure is lit only once a result exists, so the strip never claims more than
 * the readiness and outcome data show.
 */
const OPERATING_PATH: Array<{ stage: string; rung: number | "results" }> = [
  { stage: "Detect", rung: 1 },
  { stage: "Understand", rung: 1 },
  { stage: "Decide", rung: 2 },
  { stage: "Approve", rung: 3 },
  { stage: "Act", rung: 3 },
  { stage: "Measure", rung: "results" },
]

function OperatingPath({ earned, hasResults }: { earned: number; hasResults: boolean }) {
  return (
    <ol className="grid grid-cols-3 gap-2 sm:grid-cols-6" aria-label="Operating path">
      {OPERATING_PATH.map(({ stage, rung }, index) => {
        const on = rung === "results" ? hasResults : earned >= rung
        return (
          <li key={stage} className="flex min-w-0 flex-col gap-1.5">
            <span
              aria-hidden
              className={cn(
                "h-1 rounded-full",
                on ? "bg-[color:var(--g-emerald)]" : "bg-[color:var(--g-border-default)]",
              )}
            />
            <span className="flex items-baseline gap-1.5">
              <span className="font-mono text-[10px] text-muted-foreground">{String(index + 1).padStart(2, "0")}</span>
              <span className={cn("truncate text-[13px] font-medium", on ? "text-foreground" : "text-muted-foreground")}>
                {stage}
              </span>
            </span>
            <span className="sr-only">{on ? "enabled" : "not enabled yet"}</span>
          </li>
        )
      })}
    </ol>
  )
}

function Stat({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "brand" | "neutral" }) {
  return (
    <div className="min-w-0">
      <p
        className={cn(
          "truncate text-xl font-semibold tabular-nums tracking-[-0.01em]",
          tone === "brand" ? "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]" : "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function formatImpact(outcomes: PlayOutcomesResponse["outcomes"]): string {
  const verified = outcomes.filter(
    (row) => row.metadata?.verification_state === "VERIFIED SUCCESS" && typeof row.metadata?.delta_value === "number",
  )
  if (verified.length === 0) return "None yet"
  const currencies = new Set(verified.map((row) => row.metadata?.currency ?? ""))
  // Mixed or unit-less deltas can't be summed into one honest number.
  if (currencies.size !== 1) return `${verified.length} verified`
  const currency = [...currencies][0]
  const total = verified.reduce((sum, row) => sum + (row.metadata?.delta_value ?? 0), 0)
  if (!currency) return total.toLocaleString()
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(total)
  } catch {
    return `${currency} ${total.toLocaleString()}`
  }
}

export default function PlayDetailPage() {
  const params = useParams<{ key: string }>()
  const key = params.key
  const { data, error, isLoading, mutate } = useSWR<Payload>(key ? `/api/plays/${key}/readiness` : null, fetcher)
  const { data: installationData } = useSWR<{ installation: { id: string; operatingMode: string; status: string } | null }>(key ? `/api/plays/${key}/installation` : null, fetcher)
  // Same key as PlayResults, so SWR shares one request between the header stats and the list.
  const { data: outcomesData } = useSWR<PlayOutcomesResponse>(key ? `/api/plays/${key}/outcomes` : null, fetcher, { refreshInterval: 30_000 })

  const playMissing = Boolean(data) && (!data?.play || !data?.readiness)
  const outcomes = outcomesData?.outcomes ?? []

  return (
    <AppShell title={data?.play?.name ?? "Play"}>
      <div className="mx-auto max-w-6xl space-y-5 pb-8" data-composition="operate">
        <GravitrePageHeader
          eyebrow="Plays"
          title={isLoading ? "Loading…" : data?.play?.name ?? "Play"}
          description={data?.play?.objective}
          icon={<PlayCircle className="h-5 w-5" />}
          actions={<Button variant="ghost" size="sm" className="min-h-11" asChild><Link href="/plays"><ArrowLeft className="size-4" />Back to plays</Link></Button>}
        />

        <div className="space-y-5 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error ? (
            <div className="space-y-4">
              <Illustration name="moment-error" width={160} />
              <WorkSectionErrorCard title="Could not load play" message={error instanceof Error ? error.message : "Unknown error"} onRetry={() => void mutate()} />
            </div>
          ) : playMissing ? (
            <section className="border-y border-divide py-6">
              <Illustration name="moment-focus-time" width={150} className="mb-4" />
              <h2 className="text-base font-semibold text-foreground">This play isn&apos;t available</h2>
              <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground">
                No play matches <span className="font-mono text-foreground">{key}</span> in this workspace. It may have been renamed or removed from the catalog.
              </p>
              <Button size="sm" variant="outline" className="mt-4 min-h-11" asChild><Link href="/plays">Browse plays</Link></Button>
            </section>
          ) : isLoading || !data ? <Skeleton className="h-72 rounded-[10px]" /> : (
            <>
              {/* Status band: where this Play stands, in one glance. */}
              <section
                aria-label="Play status"
                className="overflow-hidden rounded-[12px] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)]"
              >
                <div className="flex flex-col gap-5 p-4 sm:p-5 lg:flex-row lg:items-center lg:justify-between lg:gap-8">
                  <div className="min-w-0 space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Operating at</p>
                    <p className="flex items-center gap-2 text-lg font-semibold text-foreground">
                      <span
                        aria-hidden
                        className={cn(
                          "size-2.5 rounded-full",
                          data.readiness.observe_ready ? "bg-[color:var(--g-emerald)]" : "bg-warning",
                        )}
                      />
                      {mode(data.readiness)}
                    </p>
                    <p className="text-[13px] text-muted-foreground">
                      {data.readiness.observe_ready ? "Ready with your workspace" : "Finish setup to use this play"}
                    </p>
                  </div>
                  <div className="grid grid-cols-3 gap-4 sm:gap-8 lg:min-w-[420px]">
                    <Stat label="Verified impact" value={formatImpact(outcomes)} tone="brand" />
                    <Stat label="Results tracked" value={outcomesData ? outcomes.length.toLocaleString() : "—"} />
                    <Stat label="Linked workflows" value={data.workflowBindingCount.toLocaleString()} />
                  </div>
                </div>
                <div className="border-t border-[color:var(--g-brand-border)] bg-[color:var(--g-surface-1)]/60 px-4 py-3.5 sm:px-5">
                  <OperatingPath earned={earnedRungs(data.readiness)} hasResults={outcomes.length > 0} />
                </div>
                {(data.readiness.blockers?.length ?? 0) > 0 || !data.readiness.observe_ready ? (
                  <div className="border-t border-warning/30 bg-warning/10 px-4 py-3 sm:px-5">
                    {(data.readiness.blockers?.length ?? 0) > 0 ? (
                      <ul className="space-y-1">
                        {data.readiness.blockers!.map((blocker) => (
                          <li key={blocker} className="flex items-start gap-2 text-[13px] text-foreground">
                            <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                            {blocker}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {!data.readiness.observe_ready ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" className="min-h-11" asChild><Link href="/connectors">Connect data <ArrowRight className="size-4" /></Link></Button>
                        <Button size="sm" variant="outline" className="min-h-11" asChild><Link href="/workflows">Review workflows</Link></Button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </section>

              <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
                <div className="min-w-0 space-y-5">
                  <PlayRunControl playKey={data.play.key} installation={installationData?.installation ?? null} readiness={data.readiness} />
                  <PlayResults playKey={data.play.key} />
                </div>

                <aside className="min-w-0 space-y-5" aria-label="Play controls">
                  <div className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4">
                    <AuthorityLadder readiness={data.readiness} />
                  </div>
                  <PlaySetup playKey={data.play.key} playVersion={data.play.version} readiness={data.readiness} />
                  <div className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <Workflow className="size-4 text-[color:var(--g-emerald)]" aria-hidden />
                      {data.workflowBindingCount} linked workflow{data.workflowBindingCount === 1 ? "" : "s"}
                    </div>
                    <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
                      This Play coordinates existing Gravitre capabilities. Workflows remain the execution authority, and verified business results require source-of-record evidence.
                    </p>
                    <Button className="-ml-2 mt-2 min-h-11" variant="ghost" size="sm" asChild><Link href="/workflows">View workflows <ArrowRight className="size-4" /></Link></Button>
                  </div>
                </aside>
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
