"use client"

import useSWR from "swr"
import Link from "next/link"
import { useParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Target } from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { cn } from "@/lib/utils"

interface GoalProgressPayload {
  goal: {
    id: string
    objective: string
    status?: string
    category?: string | null
    department?: string | null
  }
  completionPercentage: number
  milestoneStatus: Array<{ id: string; title: string; status: string }>
}

export default function GoalDetailPage() {
  const params = useParams<{ id: string }>()
  const goalId = params.id

  const { data, error, isLoading, mutate } = useSWR<GoalProgressPayload>(
    goalId ? `/api/goals/${goalId}/progress` : null,
    fetcher
  )

  return (
    <AppShell title={data?.goal.objective ?? "Goal"}>
      <div className="mx-auto max-w-3xl space-y-6 pb-6">
        <GravitrePageHeader
          eyebrow="Goals"
          title={
            isLoading
              ? "Loading…"
              : error
                ? "Could not load goal"
                : (data?.goal.objective ?? "Goal")
          }
          description={
            data?.goal.department
              ? `Department: ${data.goal.department}`
              : undefined
          }
          icon={<Target className="h-5 w-5" />}
          actions={
            <Button variant="ghost" size="sm" asChild className="gap-2">
              <Link href="/goals">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Link>
            </Button>
          }
        >
          {data ? (
            <div className="flex flex-wrap gap-2 pt-1">
              {data.goal.status ? (
                <Badge variant="outline" className="capitalize">
                  {data.goal.status}
                </Badge>
              ) : null}
              {data.goal.category ? (
                <Badge variant="outline" className="capitalize">
                  {data.goal.category}
                </Badge>
              ) : null}
            </div>
          ) : null}
        </GravitrePageHeader>

        <div className="space-y-6 px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]">
          {error ? (
            <WorkSectionErrorCard
              title="Could not load goal"
              message={error instanceof Error ? error.message : "Unknown error"}
              onRetry={() => void mutate()}
            />
          ) : isLoading || !data ? (
            <Skeleton className="h-48 w-full rounded-xl" />
          ) : (
            <>
              <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] p-6">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-medium text-foreground">{data.completionPercentage}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, data.completionPercentage))}%` }}
                  />
                </div>
              </div>

              {data.milestoneStatus.length > 0 ? (
                <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] p-6">
                  <h2 className="mb-4 text-sm font-medium text-foreground">Plan milestones</h2>
                  <div className="space-y-3">
                    {data.milestoneStatus.map((milestone) => (
                      <div
                        key={milestone.id}
                        className="flex items-center justify-between rounded-lg border border-divide/60 px-3 py-2"
                      >
                        <span className="text-sm text-foreground">{milestone.title}</span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "capitalize",
                            milestone.status === "completed"
                              ? "border-success/30 text-success"
                              : milestone.status === "in_progress"
                                ? "border-blue-500/30 text-blue-400"
                                : "border-zinc-500/30 text-zinc-400"
                          )}
                        >
                          {milestone.status.replace("_", " ")}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
