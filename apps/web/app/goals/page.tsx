"use client"

import { PAGE_FRAME } from "@/lib/design-system"
import { useCallback, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
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
import { SURFACE_COPY } from "@/lib/surface-copy"

const statusStyles: Record<string, string> = {
  draft: "bg-[color:var(--g-surface-2)] text-muted-foreground",
  active: "bg-success/10 text-success",
  paused: "bg-warning/10 text-warning",
  completed: "bg-[color:var(--g-surface-3)] text-foreground",
  cancelled: "bg-destructive/10 text-destructive",
}

function formatDate(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function GoalRow({ goal, index }: { goal: GoalRecord; index: number }) {
  const status = goal.status ?? "draft"
  return (
    <motion.li
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: Math.min(index, 8) * 0.03 }}
    >
    <Link
      href={`/goals/${goal.id}`}
      className="group block px-4 py-3.5 transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm font-medium text-foreground">
            {goal.objective}
          </p>
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
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge className={cn("capitalize", statusStyles[status] ?? statusStyles.draft)}>
            {status}
          </Badge>
          <span className="text-xs text-muted-foreground">{formatDate(goal.createdAt)}</span>
        </div>
      </div>
    </Link>
    </motion.li>
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
      <div className={PAGE_FRAME}>
        <GravitrePageHeader
          title={SURFACE_COPY.pages.goals.title}
          description={SURFACE_COPY.pages.goals.description}
          icon={<Target className="h-5 w-5" />}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={refreshGoals} aria-label="Refresh goals">
                <RefreshCw className="size-4" />
              </Button>
              <Button onClick={() => setWizardOpen(true)}>
                <Plus className="size-4" />
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
          <ul className="divide-y divide-[color:var(--g-border-subtle)] overflow-hidden rounded-[var(--np-radius-lg)] border border-[color:var(--g-border-default)] bg-card">
            {goals.map((goal, index) => (
              <GoalRow key={goal.id} goal={goal} index={index} />
            ))}
          </ul>
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
