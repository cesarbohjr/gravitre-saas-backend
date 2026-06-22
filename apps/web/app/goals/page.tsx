"use client"

import { useCallback, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
import { EmptyState } from "@/components/gravitre/empty-state"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Target, Plus, RefreshCw } from "lucide-react"
import {
  fetchGoalList,
  GOALS_REFRESH_KEY,
  type GoalRecord,
} from "@/lib/goals-list"
import { cn } from "@/lib/utils"

const statusStyles: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  active: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  paused: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  completed: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  cancelled: "bg-red-500/10 text-red-400 border-red-500/20",
}

function formatDate(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function GoalRow({ goal }: { goal: GoalRecord }) {
  const status = goal.status ?? "draft"
  return (
    <Link
      href={`/goals/${goal.id}`}
      className="block rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:border-violet-500/30 hover:bg-card/70"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground line-clamp-2">{goal.objective}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {goal.category ? <span className="capitalize">{goal.category}</span> : null}
            {goal.department ? (
              <>
                <span aria-hidden>·</span>
                <span>{goal.department}</span>
              </>
            ) : null}
            {goal.priority ? (
              <>
                <span aria-hidden>·</span>
                <span className="capitalize">{goal.priority} priority</span>
              </>
            ) : null}
          </div>
        </div>
        <Badge variant="outline" className={cn("shrink-0 capitalize", statusStyles[status] ?? statusStyles.draft)}>
          {status}
        </Badge>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Created {formatDate(goal.createdAt)}</p>
    </Link>
  )
}

export default function GoalsPage() {
  const [wizardOpen, setWizardOpen] = useState(false)
  const { data, error, isLoading, mutate } = useSWR(GOALS_REFRESH_KEY, fetchGoalList, {
    refreshInterval: 30_000,
  })

  const goals = data ?? []
  const refreshGoals = useCallback(() => {
    void mutate()
  }, [mutate])

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <PageHeader
          title="Goals"
          description="Define business outcomes and generate governed workflow plans from real org data."
          icon={Target}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={refreshGoals} className="gap-2">
                <RefreshCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setWizardOpen(true)} className="gap-2 bg-violet-600 hover:bg-violet-700">
                <Plus className="h-4 w-4" />
                New goal
              </Button>
            </div>
          }
        />

        {error ? (
          <WorkSectionErrorCard
            title="Could not load goals"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={refreshGoals}
          />
        ) : isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : goals.length === 0 ? (
          <EmptyState
            icon={Target}
            title="No goals yet"
            description="Create a goal to generate an AI workflow plan tied to your connectors and approval gates."
            action={{
              label: "Create your first goal",
              onClick: () => setWizardOpen(true),
            }}
          />
        ) : (
          <div className="space-y-3">
            {goals.map((goal) => (
              <GoalRow key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </div>

      <GoalWorkflowWizard
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        onGoalSaved={refreshGoals}
      />
    </AppShell>
  )
}
