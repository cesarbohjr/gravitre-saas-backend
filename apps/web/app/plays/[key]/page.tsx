"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/fetcher"
import { TYPE } from "@/lib/design-system"
import { ArrowLeft, ArrowRight, CheckCircle2, CircleAlert, PlayCircle } from "lucide-react"
import { PlaySetup } from "@/components/plays/play-setup"
import { PlayRunControl } from "@/components/plays/play-run-control"
import { PlayResults } from "@/components/plays/play-results"

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

export default function PlayDetailPage() {
  const params = useParams<{ key: string }>()
  const key = params.key
  const { data, error, isLoading, mutate } = useSWR<Payload>(key ? `/api/plays/${key}/readiness` : null, fetcher)
  const { data: installationData } = useSWR<{ installation: { id: string; operatingMode: string; status: string } | null }>(key ? `/api/plays/${key}/installation` : null, fetcher)

  return (
    <AppShell title={data?.play.name ?? "Play"}>
      <div className="mx-auto max-w-4xl space-y-6 pb-8" data-composition="operate">
        <GravitrePageHeader
          eyebrow="Plays"
          title={isLoading ? "Loading…" : data?.play.name ?? "Play"}
          description={data?.play.objective}
          icon={<PlayCircle className="h-5 w-5" />}
          actions={<Button variant="ghost" size="sm" asChild><Link href="/plays"><ArrowLeft className="size-4" />Back to plays</Link></Button>}
        >
          {data ? <Badge variant="outline">{mode(data.readiness)}</Badge> : null}
        </GravitrePageHeader>

        <div className="space-y-5 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error ? (
            <WorkSectionErrorCard title="Could not load play" message={error instanceof Error ? error.message : "Unknown error"} onRetry={() => void mutate()} />
          ) : isLoading || !data ? <Skeleton className="h-72 rounded-[10px]" /> : (
            <>
              <section className="border-b border-divide py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className={TYPE.eyebrow}>Readiness</p>
                    <h2 className="mt-1 text-base font-semibold">{data.readiness.observe_ready ? "Ready with your workspace" : "Finish setup to use this play"}</h2>
                  </div>
                  {data.readiness.observe_ready ? <CheckCircle2 className="size-5 text-success" /> : <CircleAlert className="size-5 text-warning" />}
                </div>
                {(data.readiness.blockers?.length ?? 0) > 0 ? (
                  <ul className="mt-4 space-y-2">
                    {data.readiness.blockers!.map((blocker) => <li key={blocker} className="border-b border-divide py-2 text-sm text-muted-foreground last:border-0">{blocker}</li>)}
                  </ul>
                ) : null}
                {!data.readiness.observe_ready ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button size="sm" className="min-h-11" asChild><Link href="/connectors">Connect data <ArrowRight className="size-4" /></Link></Button>
                    <Button size="sm" variant="outline" className="min-h-11" asChild><Link href="/workflows">Review workflows</Link></Button>
                  </div>
                ) : null}
              </section>

              <section className="border-b border-divide py-4">
                <p className={TYPE.eyebrow}>Operating path</p>
                <ol className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-sm">
                  {["Detect", "Understand", "Decide", "Approve", "Act", "Measure"].map((stage, index) => (
                    <li key={stage} className="text-foreground">
                      <span className="font-mono text-[11px] text-muted-foreground">{String(index + 1).padStart(2, "0")}</span> {stage}
                    </li>
                  ))}
                </ol>
                <p className="mt-3 text-xs text-muted-foreground">This Play coordinates existing Gravitre capabilities. Workflows remain the execution authority, and verified business results require source-of-record evidence.</p>
              </section>

              <PlaySetup playKey={data.play.key} playVersion={data.play.version} readiness={data.readiness} />

              <PlayRunControl playKey={data.play.key} installation={installationData?.installation ?? null} readiness={data.readiness} />

              <PlayResults playKey={data.play.key} />

              <section className="grid gap-4 border-t border-divide py-4 sm:grid-cols-2">
                <div>
                  <p className={TYPE.eyebrow}>Linked workflows</p>
                  <p className="mt-1 text-2xl font-semibold">{data.workflowBindingCount}</p>
                  <Button className="mt-4 min-h-11" variant="ghost" size="sm" asChild><Link href="/workflows">View workflows <ArrowRight className="size-4" /></Link></Button>
                </div>
                <div>
                  <p className={TYPE.eyebrow}>Current operating capability</p>
                  <p className="mt-1 text-lg font-semibold">{mode(data.readiness)}</p>
                  <p className="mt-2 text-xs text-muted-foreground">This reflects current readiness. Saved authority can never exceed these validated controls.</p>
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
