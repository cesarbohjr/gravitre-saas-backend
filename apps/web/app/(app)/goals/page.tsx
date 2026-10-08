"use client"

import { PAGE_FRAME, TYPE } from "@/lib/design-system"
import { useCallback, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitrePageHeader,
  LiveStatus,
} from "@/components/gravitre/nodus-product"
import {
  OperatingEmpty,
  PhaseBand,
} from "@/components/gravitre/operating/operating-primitives"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { GoalWorkflowWizard } from "@/components/gravitre/goal-workflow-wizard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
  if (!value) return "Not reported"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Not reported"
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function GoalRow({ goal, index }: { goal: GoalRecord; index: number }) {
  const reduced = useReducedMotion()
  const status =
    goal.status && statusStyles[goal.status] ? goal.status : "unreported"
  return (
    <motion.li
      initial={reduced ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{
        duration: reduced ? 0 : 0.18,
        delay: reduced ? 0 : Math.min(index, 5) * 0.02,
      }}
    >
      <Link
        href={`/goals/${goal.id}`}
        className="group block px-[var(--np-page-pad-sm)] py-3.5 transition-colors sm:px-[var(--np-page-pad)] hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <div className="flex flex-col items-start justify-between gap-3 sm:flex-row">
          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 text-sm font-medium text-foreground">
              {goal.objective || "Objective not reported"}
            </p>
            {typeof goal.successMetrics?.primary === "string" &&
            goal.successMetrics.primary ? (
              <p className="mt-1 text-sm text-muted-foreground">
                Success measure: {goal.successMetrics.primary}
              </p>
            ) : null}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {goal.category ? (
                <span className="capitalize">{goal.category}</span>
              ) : null}
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
          <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:flex-col sm:items-end sm:gap-1">
            <Badge
              className={cn(
                "capitalize",
                statusStyles[status] ?? statusStyles.draft,
              )}
            >
              {status === "unreported" ? "Not reported" : status}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatDate(goal.createdAt)}
            </span>
          </div>
        </div>
      </Link>
    </motion.li>
  )
}

export default function GoalsPage() {
  const [search, setSearch] = useState("")
  const [department, setDepartment] = useState("")
  const [order, setOrder] = useState("recent")
  const [wizardOpen, setWizardOpen] = useState(false)
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    GOALS_REFRESH_KEY,
    fetchGoalList,
    {
      refreshInterval: 30_000,
    },
  )

  const [phase, setPhase] = useState<string | null>(null)
  const allGoals = useMemo(() => data ?? [], [data])
  const known = (goal: GoalRecord) =>
    goal.status && statusStyles[goal.status] ? goal.status : "unreported"
  const departments = [
    ...new Set(
      allGoals.map((g) => g.department).filter((v): v is string => Boolean(v)),
    ),
  ].sort()
  const goals = allGoals
    .filter(
      (goal) =>
        (!phase || known(goal) === phase) &&
        (!department || goal.department === department) &&
        `${goal.objective} ${goal.department ?? ""} ${goal.category ?? ""}`
          .toLowerCase()
          .includes(search.trim().toLowerCase()),
    )
    .sort((a, b) =>
      order === "priority"
        ? (["high", "medium", "low"].indexOf(a.priority ?? "") < 0
            ? 3
            : ["high", "medium", "low"].indexOf(a.priority!)) -
          (["high", "medium", "low"].indexOf(b.priority ?? "") < 0
            ? 3
            : ["high", "medium", "low"].indexOf(b.priority!))
        : (Date.parse(b.createdAt ?? "") || 0) -
          (Date.parse(a.createdAt ?? "") || 0),
    )
  const countOf = (status: string) =>
    allGoals.filter((goal) => known(goal) === status).length
  const activeGoals = countOf("active")
  const refreshGoals = useCallback(() => {
    void mutate()
  }, [mutate])

  return (
    <AppShell>
      <div className={PAGE_FRAME} data-composition="operate">
        <GravitrePageHeader
          title={SURFACE_COPY.pages.goals.title}
          description={SURFACE_COPY.pages.goals.description}
          icon={<Target className="h-5 w-5" />}
          status={
            allGoals.length > 0 ? (
              <LiveStatus tone={activeGoals > 0 ? "live" : "idle"}>
                {activeGoals > 0
                  ? `${activeGoals} objective${activeGoals === 1 ? "" : "s"} in motion`
                  : "No objective in motion"}
              </LiveStatus>
            ) : undefined
          }
          actions={
            <div className="flex flex-wrap items-center gap-2 [&_[data-slot=button]]:min-h-11">
              <Button
                variant="ghost"
                size="icon"
                className="min-w-11"
                disabled={isValidating}
                onClick={refreshGoals}
                aria-label="Refresh goals"
              >
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
            message="Your last loaded goals remain available. Try again to refresh the list."
            onRetry={refreshGoals}
          />
        ) : null}
        {isLoading && !data ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        ) : !data ? null : allGoals.length === 0 ? (
          <div className="py-4">
          <Illustration name="moment-milestone" width={180} className="mb-2" />
          <OperatingEmpty
            className="px-0 sm:px-0"
            title="No objectives yet"
            body="A goal states the outcome you want. Gravitre drafts a plan tied to your connectors and approval gates, agents carry out the work, and results are measured against the goal."
            path={[
              "Set the objective",
              "Plan the work",
              "Agents execute",
              "Measure the outcome",
            ]}
            action={
              <Button onClick={() => setWizardOpen(true)}>
                <Plus className="size-4" />
                Create your first goal
              </Button>
            }
          />
          </div>
        ) : (
          <div className="space-y-4 -mx-[var(--np-page-pad-sm)] sm:-mx-[var(--np-page-pad)]">
            <div className="grid gap-3 px-4 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
              <Input
                className="min-h-11"
                aria-label="Search goals"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search objectives, categories or departments"
              />
              <select
                aria-label="Goal department"
                className="min-h-11 rounded-md border border-input bg-background px-3 text-sm"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
              >
                <option value="">All departments</option>
                {departments.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
              <select
                aria-label="Sort goals"
                className="min-h-11 rounded-md border border-input bg-background px-3 text-sm"
                value={order}
                onChange={(e) => setOrder(e.target.value)}
              >
                <option value="recent">Newest first</option>
                <option value="priority">Highest priority</option>
              </select>
            </div>
            <PhaseBand
              label="Goal phases"
              phases={[
                {
                  id: "active",
                  label: "In motion",
                  count: activeGoals,
                  tone: "live",
                },
                {
                  id: "draft",
                  label: "Draft",
                  count: countOf("draft"),
                  tone: "neutral",
                },
                {
                  id: "paused",
                  label: "Paused",
                  count: countOf("paused"),
                  tone: "attention",
                },
                {
                  id: "completed",
                  label: "Completed",
                  count: countOf("completed"),
                  tone: "done",
                },
                {
                  id: "cancelled",
                  label: "Cancelled",
                  count: countOf("cancelled"),
                  tone: "neutral",
                },
                ...(countOf("unreported")
                  ? [
                      {
                        id: "unreported",
                        label: "Not reported",
                        count: countOf("unreported"),
                        tone: "neutral" as const,
                      },
                    ]
                  : []),
              ]}
              active={phase}
              onSelect={setPhase}
            />
            <div className="flex flex-wrap items-center justify-between gap-2 px-4">
              <p className={TYPE.meta}>
                {goals.length} of {allGoals.length} loaded goals
              </p>
              {phase || search || department ? (
                <Button
                  className="min-h-11"
                  variant="ghost"
                  onClick={() => {
                    setPhase(null)
                    setSearch("")
                    setDepartment("")
                  }}
                >
                  Clear filters
                </Button>
              ) : null}
            </div>
            {goals.length === 0 ? (
              <div className="px-[var(--np-page-pad-sm)] pt-6 sm:px-[var(--np-page-pad)]">
                <Illustration name="moment-focus-time" width={150} />
                <OperatingEmpty className="px-0 pt-3 sm:px-0" title="No goals match these filters" />
              </div>
            ) : (
              <ul className="divide-y divide-[color:var(--g-border-subtle)] border-b border-[color:var(--g-border-default)]">
                {goals.map((goal, index) => (
                  <GoalRow key={goal.id} goal={goal} index={index} />
                ))}
              </ul>
            )}
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
