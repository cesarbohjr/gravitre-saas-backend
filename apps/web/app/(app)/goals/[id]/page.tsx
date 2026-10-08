"use client"

import useSWR from "swr"
import Link from "next/link"
import { useParams } from "next/navigation"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Target } from "lucide-react"
import { GoalProgressSummary, MilestoneTrack } from "@/components/goals/goal-progress"
import { fetcher } from "@/lib/fetcher"

interface GoalProgressPayload {
  goal: { id: string; objective: string; status?: string; category?: string | null; department?: string | null }
  completionPercentage?: number | null
  milestoneStatus?: Array<{ id: string; title: string; status?: string }> | null
}

export default function GoalDetailPage() {
  const { id: goalId } = useParams<{ id: string }>()
  const { data, error, isLoading, mutate } = useSWR<GoalProgressPayload>(goalId ? `/api/goals/${goalId}/progress` : null, fetcher)
  usePublishGravitreAISelection(data?.goal ? { kind: "goal", id: data.goal.id, label: data.goal.objective } : null)
  const reported = data?.completionPercentage
  const progress = typeof reported === "number" && Number.isFinite(reported) ? Math.min(100, Math.max(0, reported)) : null
  const milestones = data?.milestoneStatus

  return (
    <AppShell title={data?.goal?.objective ?? "Goal"}>
      <div className="mx-auto max-w-4xl space-y-6 pb-[calc(80px+env(safe-area-inset-bottom))]" data-composition="operate">
        <GravitrePageHeader
          eyebrow="Goals"
          title={data?.goal?.objective ?? (isLoading ? "Loading…" : error ? "Could not load goal" : "Goal")}
          description={data?.goal?.department ? `Department: ${data.goal.department}` : undefined}
          icon={<Target className="h-5 w-5" />}
          actions={<div className="flex flex-wrap items-center gap-2"><AskGravitreSummonButton label="Review this goal" prompt="Review progress and reported milestones for this goal, and suggest the next useful action." /><Button variant="ghost" size="sm" asChild className="min-h-11 gap-2"><Link href="/goals"><ArrowLeft className="h-4 w-4" />Back to goals</Link></Button></div>}
        >
          {data?.goal ? <div className="flex flex-wrap gap-2 pt-1">
            {data.goal.status ? <Badge variant="outline" className="capitalize">{data.goal.status.replaceAll("_", " ")}</Badge> : null}
            {data.goal.category ? <Badge variant="outline" className="capitalize">{data.goal.category}</Badge> : null}
          </div> : null}
        </GravitrePageHeader>
        <div className="space-y-6 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error && !data ? <Illustration name="moment-error" width={160} /> : null}
          {error ? <WorkSectionErrorCard title={data ? "Could not refresh goal" : "Could not load goal"} message={data ? "Showing the last retrieved goal. Retry for the current state." : error instanceof Error ? error.message : "Try again to retrieve this goal."} onRetry={() => void mutate()} /> : null}
          {isLoading && !data ? <Skeleton className="h-48 w-full" /> : data ? <>
            <GoalProgressSummary progress={progress} milestones={milestones ?? null} />
            <section aria-labelledby="goal-milestones-heading">
              <h2 id="goal-milestones-heading" className="font-sans text-xl font-medium">Plan milestones</h2>
              {milestones == null ? <p className="mt-4 text-sm text-muted-foreground">Milestones not reported.</p> : milestones.length === 0 ? <div className="mt-4"><Illustration name="moment-focus-time" width={140} className="mb-3" /><p className="text-sm text-muted-foreground">No milestones have been added to this goal.</p></div> : <MilestoneTrack milestones={milestones} />}
            </section>
          </> : !error && !isLoading ? <p className="text-sm text-muted-foreground">Goal details not reported.</p> : null}
        </div>
      </div>
    </AppShell>
  )
}
