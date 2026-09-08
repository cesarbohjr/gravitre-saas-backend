"use client"

import { useCallback, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
} from "@/components/gravitre/nodus-product"
import { AnimatedCounter } from "@/components/gravitre/premium-effects"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Icon } from "@/lib/icons"
import { NavTasks } from "@/components/icons/nodus-nav/outline"
import { cn } from "@/lib/utils"
import { INTERACTION } from "@/lib/design-system"
import { type DemoAssignment } from "@/lib/demo-assignments"
import {
  ASSIGNMENTS_REFRESH_KEY,
  fetchAssignmentList,
} from "@/lib/assignments-list"
import { NewAssignmentModal } from "@/components/gravitre/assignments/new-assignment-modal"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { useMotionPrefs, entranceContainer, reducedEntranceContainer, entranceItem, reducedEntranceItem } from "@/lib/animations"
import { useAuth } from "@/lib/auth-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { 
  Megaphone, 
  TrendingUp, 
  Database, 
  PieChart, 
  Headphones,
  RefreshCw,
  LayoutGrid,
  Rows3,
  type LucideIcon 
} from "lucide-react"
import { SegmentedControl } from "@/components/gravitre/filter-chip"

type Assignment = DemoAssignment

// Agent icon mapping based on role
const agentIcons: Record<string, LucideIcon> = {
  "Marketing Agent": Megaphone,
  "Marketing Operator": Megaphone,
  "Sales Assistant": TrendingUp,
  "Data Quality Agent": Database,
  "Finance Reporter": PieChart,
  "Support Coordinator": Headphones,
}

const initialAssignments: Assignment[] = []

const ASSIGNMENTS_REFRESH_MS = 15_000

const statusConfig: Record<string, { label: string; color: string; bgColor: string; dotColor: string; icon: string }> = {
  running: { label: "Running", color: "text-info", bgColor: "bg-info/10", dotColor: "bg-info", icon: "activity" },
  completed: { label: "Completed", color: "text-[color:var(--g-brand)]", bgColor: "bg-[color:var(--g-brand-soft)]", dotColor: "bg-[color:var(--g-brand)]", icon: "check" },
  pending: { label: "Queued", color: "text-amber-700", bgColor: "bg-amber-500/10", dotColor: "bg-amber-500", icon: "clock" },
  failed: { label: "Failed", color: "text-destructive", bgColor: "bg-destructive/10", dotColor: "bg-destructive", icon: "warning" },
  needs_approval: { label: "Needs Approval", color: "text-violet-700", bgColor: "bg-violet-500/10", dotColor: "bg-violet-500", icon: "shield" },
}

function deriveAssignmentProgress(assignment: DemoAssignment): number {
  if (Number.isFinite(assignment.progress)) {
    return Math.max(0, Math.min(100, assignment.progress))
  }
  const total = assignment.steps.length
  if (total === 0) return 0
  const done = assignment.steps.filter((step) => step.status === "done").length
  const hasRunning = assignment.steps.some((step) => step.status === "running")
  return Math.round(((done + (hasRunning ? 0.5 : 0)) / total) * 100)
}

function getRunningStepLabel(assignment: DemoAssignment): string | null {
  if (assignment.status !== "running") return null
  if (assignment.currentStepDetail?.trim()) return assignment.currentStepDetail.trim()
  const step = assignment.steps.find((s) => s.status === "running")
  if (!step) return null
  const destination = assignment.destination.toLowerCase()
  if (destination.includes("hubspot")) {
    return "Fetching campaign data from HubSpot…"
  }
  if (destination.includes("salesforce")) {
    return "Syncing lead data from Salesforce…"
  }
  return `Running step: ${step.name}…`
}

function AssignmentProgressBar({ assignment }: { assignment: DemoAssignment }) {
  const percent = deriveAssignmentProgress(assignment)
  const runningLabel = getRunningStepLabel(assignment)

  const fillClass = cn(
    "h-full rounded-full transition-[width] duration-300 ease-out",
    assignment.status === "running" && "bg-info",
    assignment.status === "completed" && "bg-[color:var(--g-brand)]",
    assignment.status === "needs_approval" && "bg-violet-500",
    assignment.status === "failed" && "bg-destructive",
    assignment.status === "pending" && "bg-amber-500/70",
  )

  return (
    <div className="mb-3">
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className="relative h-2 w-full cursor-default overflow-hidden rounded-full bg-[color:var(--g-surface-2)]"
              aria-label={`${percent}% complete`}
            >
              <div className={fillClass} style={{ width: `${percent}%` }} />
            </div>
          </TooltipTrigger>
          <TooltipContent side="top">{percent}% complete</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {runningLabel ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-info">
          <RefreshCw className="h-3 w-3 shrink-0 animate-spin" />
          <span className="line-clamp-1">{runningLabel}</span>
        </p>
      ) : null}
    </div>
  )
}

// Live Activity Pulse
function ActivityPulse() {
  return (
    <div className="relative flex items-center gap-2">
      <div className="relative h-2.5 w-2.5">
        <div className="absolute inset-0 animate-ping rounded-full bg-[color:var(--g-brand)] opacity-60" />
        <div className="relative h-full w-full rounded-full bg-[color:var(--g-brand)]" />
      </div>
      <span className="text-xs font-medium text-[color:var(--g-brand)]">Live</span>
    </div>
  )
}

// Assignment Card with Rich Detail
function AssignmentCard({
  assignment,
  onNavigate,
  onOpenApproval,
}: {
  assignment: Assignment
  onNavigate: () => void
  onOpenApproval?: () => void
}) {
  const status = statusConfig[assignment.status]
  const { reduced } = useMotionPrefs()

  return (
    <motion.div
      layout
      variants={reduced ? reducedEntranceItem : entranceItem}
      whileHover={reduced ? undefined : { 
        y: -6, 
        scale: 1.01,
        transition: { duration: 0.15, ease: [0.2, 0, 0, 1] }
      }}
      whileTap={reduced ? undefined : { scale: 0.99 }}
      role="button"
      tabIndex={0}
      aria-label={`Open assignment: ${assignment.title}`}
      onClick={onNavigate}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onNavigate()
        }
      }}
      className={cn(
        "group relative cursor-pointer overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)] transition-colors hover:bg-[color:var(--g-surface-2)] sm:p-5",
        INTERACTION,
      )}
    >
      {/* Status indicator line */}
      <div className={cn(
        "absolute left-0 right-0 top-0 h-0.5",
        assignment.status === "running" && "bg-info",
        assignment.status === "completed" && "bg-[color:var(--g-brand)]",
        assignment.status === "pending" && "bg-amber-500",
        assignment.status === "failed" && "bg-destructive",
        assignment.status === "needs_approval" && "bg-violet-500",
      )} />

      <div className="flex items-start gap-3 sm:gap-4">
        {/* Agent Avatar */}
        <div className="relative shrink-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)] sm:h-12 sm:w-12">
            <assignment.agent.icon className="h-5 w-5 sm:h-6 sm:w-6" />
          </div>
          {assignment.status === "running" && (
            <motion.div
              className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-info"
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              <Icon name="activity" size="xs" className="text-white" />
            </motion.div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4 mb-2">
            <div>
              <h3 className="font-semibold text-foreground group-hover:text-foreground/90 transition-colors line-clamp-1">
                {assignment.title}
              </h3>
              <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                {assignment.brief}
              </p>
            </div>
            <div className={cn(
              "shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
              status.bgColor, status.color
            )}>
              <div className={cn("h-1.5 w-1.5 rounded-full", status.dotColor, assignment.status === "running" && "animate-pulse")} />
              {status.label}
            </div>
          </div>

          <AssignmentProgressBar assignment={assignment} />

          {/* Meta Row */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-[11px] sm:text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Icon name="user" size="xs" />
              <span>{assignment.agent.name}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Icon name="clock" size="xs" />
              <span>{assignment.createdAt}</span>
            </div>
            {assignment.confidence && assignment.status !== "running" && (
              <div className="flex items-center gap-1.5 ml-auto">
                <span className={cn(
                  "font-medium",
                  assignment.confidence >= 90 ? "text-[color:var(--g-brand)]" : 
                  assignment.confidence >= 70 ? "text-amber-600" : "text-destructive"
                )}>
                  {assignment.confidence}% confident
                </span>
              </div>
            )}
            {assignment.status === "needs_approval" && onOpenApproval ? (
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  onOpenApproval()
                }}
                className="ml-auto text-xs font-medium text-violet-600 underline-offset-2 hover:underline"
              >
                Approval
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Hover reveal: Quick Actions */}
      <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0"
          aria-label={`View ${assignment.title}`}
          onClick={(event) => {
            event.stopPropagation()
            onNavigate()
          }}
        >
          <Icon name="eye" size="sm" />
        </Button>
      </div>
    </motion.div>
  )
}

function AssignmentListSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]">
          <div className="flex items-start gap-4">
            <Skeleton className="h-12 w-12 shrink-0 rounded-[var(--np-radius-md)]" />
            <div className="flex-1 space-y-3">
              <Skeleton className="h-4 w-2/5" />
              <Skeleton className="h-3 w-3/5" />
              <Skeleton className="h-2 w-full rounded-full" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

type FilterAccent = "default" | "blue" | "violet" | "emerald" | "amber" | "red"

type AssignmentFilterOption = {
  id: string
  label: string
  count: number
  accent: FilterAccent
  showAttentionDot?: boolean
}

const filterAccentStyles: Record<FilterAccent, string> = {
  default: "bg-[color:var(--g-surface-1)] border-divide shadow-[var(--np-shadow)]",
  blue: "bg-info/10 border-info/25 shadow-[var(--np-shadow)]",
  violet: "bg-violet-500/10 border-violet-500/25 shadow-[var(--np-shadow)]",
  emerald: "bg-[color:var(--g-brand-soft)] border-[color:var(--g-brand-border)] shadow-[var(--np-shadow)]",
  amber: "bg-amber-500/10 border-amber-500/25 shadow-[var(--np-shadow)]",
  red: "bg-destructive/10 border-destructive/25 shadow-[var(--np-shadow)]",
}

function AssignmentFilterTabs({
  options,
  value,
  onChange,
}: {
  options: AssignmentFilterOption[]
  value: string
  onChange: (id: string) => void
}) {
  return (
    <div
      role="tablist"
      aria-label="Filter assignments by status"
      className="flex items-center gap-1 overflow-x-auto rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-1 scrollbar-none"
    >
      {options.map((option) => {
        const isActive = value === option.id
        return (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(option.id)}
            className={cn(
              "relative z-10 flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[var(--np-radius-md)] px-2.5 py-1.5 text-xs font-medium transition-colors sm:gap-2 sm:px-4 sm:py-2 sm:text-sm",
              isActive ? "font-semibold text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {isActive ? (
              <motion.span
                layoutId="assignment-filter-active"
                className={cn("absolute inset-0 rounded-[var(--np-radius-md)] border", filterAccentStyles[option.accent])}
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            ) : null}
            <span className="relative z-10 flex items-center gap-1.5">
              {option.showAttentionDot ? (
                <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-destructive" />
                </span>
              ) : null}
              {option.label}
            </span>
            <span
              className={cn(
                "relative z-10 rounded-[var(--np-radius-sm)] px-1 py-0.5 text-[10px] tabular-nums sm:px-1.5 sm:text-xs",
                isActive ? "bg-[color:var(--g-surface-2)] text-foreground" : "text-muted-foreground",
              )}
            >
              <AnimatedCounter value={option.count} duration={0.45} />
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** Options for the list/board switcher, declared once outside render. */
const ASSIGNMENT_VIEW_MODES = [
  { id: "list" as const, label: "List view", icon: Rows3 },
  { id: "kanban" as const, label: "Board view", icon: LayoutGrid },
] as const

export default function AssignmentsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const { reduced } = useMotionPrefs()
  const [localAssignments, setLocalAssignments] = useState<Assignment[]>([])
  const [filter, setFilter] = useState<string>("all")
  const [viewMode, setViewMode] = useState<"list" | "kanban">("list")
  const [newAssignmentOpen, setNewAssignmentOpen] = useState(false)

  const {
    data: fetchedAssignments,
    error: assignmentsError,
    isLoading: assignmentsLoading,
    mutate: refreshAssignments,
  } = useSWR<DemoAssignment[]>(
    user ? ASSIGNMENTS_REFRESH_KEY : null,
    fetchAssignmentList,
    {
      revalidateOnFocus: true,
      refreshInterval: ASSIGNMENTS_REFRESH_MS,
    },
  )

  const assignmentList = useMemo(() => {
    const base = !user
      ? initialAssignments
      : fetchedAssignments ?? (assignmentsLoading ? [] : initialAssignments)
    const seen = new Set(base.map((item) => item.id))
    const locals = localAssignments.filter((item) => !seen.has(item.id))
    return [...locals, ...base]
  }, [user, fetchedAssignments, assignmentsLoading, localAssignments])

  const openNewAssignment = useCallback(() => setNewAssignmentOpen(true), [])
  useWorkPageShortcut("new", openNewAssignment)
  
  const filteredAssignments = filter === "all" 
    ? assignmentList 
    : assignmentList.filter(a => a.status === filter)

  const inProgressCount = assignmentList.filter((a) => a.status === "running").length
  const completedCount = assignmentList.filter((a) => a.status === "completed").length
  const pendingApprovalCount = assignmentList.filter((a) => a.status === "needs_approval").length
  const queuedCount = assignmentList.filter((a) => a.status === "pending").length

  const filterOptions = useMemo<AssignmentFilterOption[]>(() => {
    const countByStatus = (status: DemoAssignment["status"]) =>
      assignmentList.filter((a) => a.status === status).length
    const failedCount = countByStatus("failed")

    return [
      { id: "all", label: "All", count: assignmentList.length, accent: "default" },
      { id: "running", label: "Running", count: countByStatus("running"), accent: "blue" },
      {
        id: "needs_approval",
        label: "Needs Approval",
        count: countByStatus("needs_approval"),
        accent: "violet",
      },
      { id: "completed", label: "Completed", count: countByStatus("completed"), accent: "emerald" },
      { id: "pending", label: "Queued", count: countByStatus("pending"), accent: "amber" },
      {
        id: "failed",
        label: "Failed",
        count: failedCount,
        accent: "red",
        showAttentionDot: failedCount > 0,
      },
    ]
  }, [assignmentList])

  const handleAssignmentCreated = (assignment: DemoAssignment) => {
    setLocalAssignments((current) => [assignment, ...current.filter((item) => item.id !== assignment.id)])
    setFilter("all")
    void refreshAssignments()
  }

  const showListSkeleton = Boolean(user) && assignmentsLoading && !fetchedAssignments

  return (
    <AppShell title={SURFACE_COPY.pages.assignments.title}>
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Work"
          title={SURFACE_COPY.pages.assignments.title}
          description={SURFACE_COPY.pages.assignments.description}
          icon={<NavTasks className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <ActivityPulse />
              <Button
                className="w-full gap-2 shadow-[var(--np-shadow)] sm:w-auto"
                onClick={openNewAssignment}
              >
                <Icon name="add" size="sm" />
                New Assignment
              </Button>
            </div>
          }
        />

        <div className="flex min-h-0 flex-1 flex-col gap-[var(--np-kpi-gap)] px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-6">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric
              label="In Progress"
              value={
                showListSkeleton ? "—" : <AnimatedCounter value={inProgressCount} duration={0.6} />
              }
              hint={inProgressCount > 0 ? "Running now" : "None running"}
              icon={<Icon name="activity" size="sm" />}
            />
            <GravitreMetric
              label="Completed"
              value={
                showListSkeleton ? "—" : <AnimatedCounter value={completedCount} duration={0.75} />
              }
              hint="Finished assignments"
              icon={<Icon name="check" size="sm" />}
            />
            <GravitreMetric
              label="Pending Approval"
              value={
                showListSkeleton ? (
                  "—"
                ) : (
                  <AnimatedCounter value={pendingApprovalCount} duration={0.85} />
                )
              }
              hint={pendingApprovalCount > 0 ? "Needs review" : "None waiting"}
              warning={pendingApprovalCount > 0}
              icon={<Icon name="shield" size="sm" />}
            />
            <GravitreMetric
              label="Queued"
              value={
                showListSkeleton ? "—" : <AnimatedCounter value={queuedCount} duration={0.95} />
              }
              hint="Waiting to start"
              icon={<Icon name="clock" size="sm" />}
            />
          </section>

          {/* Filter Bar */}
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center sm:gap-0">
            <AssignmentFilterTabs options={filterOptions} value={filter} onChange={setFilter} />

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="h-9 gap-2">
                <Icon name="filter" size="sm" />
                <span className="hidden sm:inline">Filter</span>
              </Button>
              <SegmentedControl
                options={ASSIGNMENT_VIEW_MODES}
                value={viewMode}
                onChange={setViewMode}
                ariaLabel="Assignment view mode"
                iconOnly
                className="bg-secondary/50"
              />
            </div>
          </div>

          {/* Assignment List */}
          {assignmentsError && !showListSkeleton ? (
            <WorkSectionErrorCard
              title="Could not load assignments"
              message="Your assignments list could not be refreshed. Showing the last loaded data if available."
              onRetry={() => void refreshAssignments()}
            />
          ) : null}

          {showListSkeleton ? (
            <AssignmentListSkeleton />
          ) : (
          <AnimatePresence mode="popLayout">
            <motion.div
              layout
              className="grid grid-cols-1 gap-4"
              variants={reduced ? reducedEntranceContainer : entranceContainer}
              initial="initial"
              animate="animate"
            >
              {filteredAssignments.map((assignment) => (
                <AssignmentCard
                  key={assignment.id}
                  assignment={assignment}
                  onNavigate={() => router.push(`/assignments/${assignment.id}`)}
                  onOpenApproval={() =>
                    router.push(`/assignments/${assignment.id}?approval=1`)
                  }
                />
              ))}
            </motion.div>
          </AnimatePresence>
          )}

          {!showListSkeleton && filteredAssignments.length === 0 && (
            <GravitreEmpty
              icon={<Icon name="tasks" size="lg" />}
              title={assignmentList.length === 0 ? "No assignments yet" : "No assignments found"}
              hint={
                assignmentList.length === 0
                  ? "Assign your first task to an AI agent on your team."
                  : "Try adjusting your filters or create a new assignment"
              }
              action={
                <Button onClick={openNewAssignment} className="gap-2">
                  <Icon name="add" size="sm" />
                  New Assignment
                </Button>
              }
            />
          )}
        </div>
      </div>

      <NewAssignmentModal
        open={newAssignmentOpen}
        onOpenChange={setNewAssignmentOpen}
        onCreated={handleAssignmentCreated}
      />
    </AppShell>
  )
}
