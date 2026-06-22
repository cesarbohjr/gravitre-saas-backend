"use client"

import useSWR from "swr"
import Link from "next/link"
import { useParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
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
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" asChild className="gap-2">
            <Link href="/goals">
              <ArrowLeft className="h-4 w-4" />
              Goals
            </Link>
          </Button>
        </div>

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
            <div className="rounded-xl border border-border/60 bg-card/40 p-6">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-violet-500/10 p-2">
                  <Target className="h-5 w-5 text-violet-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <h1 className="text-xl font-semibold text-foreground">{data.goal.objective}</h1>
                  <div className="mt-2 flex flex-wrap gap-2">
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
                </div>
              </div>
              <div className="mt-6">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-medium text-foreground">{data.completionPercentage}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-violet-500 transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, data.completionPercentage))}%` }}
                  />
                </div>
              </div>
            </div>

            {data.milestoneStatus.length > 0 ? (
              <div className="rounded-xl border border-border/60 bg-card/40 p-6">
                <h2 className="mb-4 text-sm font-medium text-foreground">Plan milestones</h2>
                <div className="space-y-3">
                  {data.milestoneStatus.map((milestone) => (
                    <div
                      key={milestone.id}
                      className="flex items-center justify-between rounded-lg border border-border/40 px-3 py-2"
                    >
                      <span className="text-sm text-foreground">{milestone.title}</span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "capitalize",
                          milestone.status === "completed"
                            ? "border-emerald-500/30 text-emerald-400"
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
    </AppShell>
  )
}
