"use client"

import { useCallback, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
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
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { type DemoAssignment } from "@/lib/demo-assignments"
import {
  ASSIGNMENTS_REFRESH_KEY,
  fetchAssignmentList,
  listFallbackAssignments,
} from "@/lib/assignments-list"
import { NewAssignmentModal } from "@/components/gravitre/assignments/new-assignment-modal"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { useMotionPrefs, entranceContainer, reducedEntranceContainer, entranceItem, reducedEntranceItem } from "@/lib/animations"
import { useAuth } from "@/lib/auth-context"
import { 
  Megaphone, 
  TrendingUp, 
  Database, 
  PieChart, 
  Headphones,
  RefreshCw,
  type LucideIcon 
} from "lucide-react"

// Types — list view uses shared demo catalog (detail resolves via fetchAssignmentJob)
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

const initialAssignments: Assignment[] = listFallbackAssignments()

const ASSIGNMENTS_REFRESH_MS = 15_000

const statusConfig: Record<string, { label: string; color: string; bgColor: string; dotColor: string; icon: string }> = {
  running: { label: "Running", color: "text-blue-400", bgColor: "bg-blue-500/10", dotColor: "bg-blue-500", icon: "activity" },
  completed: { label: "Completed", color: "text-emerald-400", bgColor: "bg-emerald-500/10", dotColor: "bg-emerald-500", icon: "check" },
  pending: { label: "Queued", color: "text-amber-400", bgColor: "bg-amber-500/10", dotColor: "bg-amber-500", icon: "clock" },
  failed: { label: "Failed", color: "text-red-400", bgColor: "bg-red-500/10", dotColor: "bg-red-500", icon: "warning" },
  needs_approval: { label: "Needs Approval", color: "text-violet-400", bgColor: "bg-violet-500/10", dotColor: "bg-violet-500", icon: "shield" },
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
    assignment.status === "running" && "bg-blue-500",
    assignment.status === "completed" && "bg-emerald-500",
    assignment.status === "needs_approval" && "bg-gradient-to-r from-violet-500 to-amber-500",
    assignment.status === "failed" && "bg-red-500",
    assignment.status === "pending" && "bg-amber-500/70",
  )

  return (
    <div className="mb-3">
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className="relative h-2 w-full cursor-default overflow-hidden rounded-full bg-muted/80"
              aria-label={`${percent}% complete`}
            >
              <div className={fillClass} style={{ width: `${percent}%` }} />
              {assignment.status === "running" && percent > 0 ? (
                <div
                  className="pointer-events-none absolute inset-y-0 left-0 overflow-hidden rounded-full"
                  style={{ width: `${percent}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-white/30 to-blue-500/0 animate-shimmer" />
                </div>
              ) : null}
            </div>
          </TooltipTrigger>
          <TooltipContent side="top">{percent}% complete</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {runningLabel ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-blue-400">
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
      <div className="relative h-3 w-3">
        <div className="absolute inset-0 rounded-full bg-emerald-500 animate-ping opacity-75" />
        <div className="relative h-full w-full rounded-full bg-emerald-500" />
      </div>
      <span className="text-xs font-medium text-emerald-400">Live</span>
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
      className="group relative overflow-hidden rounded-xl sm:rounded-2xl border border-border bg-card/80 backdrop-blur-sm p-4 sm:p-5 cursor-pointer transition-all hover:border-muted-foreground/30 hover:shadow-xl hover:shadow-black/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {/* Status indicator line */}
      <div className={cn(
        "absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl",
        assignment.status === "running" && "bg-gradient-to-r from-blue-500 via-blue-400 to-blue-500 animate-pulse",
        assignment.status === "completed" && "bg-emerald-500",
        assignment.status === "pending" && "bg-amber-500",
        assignment.status === "failed" && "bg-red-500",
        assignment.status === "needs_approval" && "bg-gradient-to-r from-violet-500 to-purple-500",
      )} />

      <div className="flex items-start gap-3 sm:gap-4">
        {/* Agent Avatar */}
        <div className="relative shrink-0">
          <div className={cn(
            "h-10 w-10 sm:h-12 sm:w-12 rounded-lg sm:rounded-xl bg-gradient-to-br flex items-center justify-center text-white",
            assignment.agent.gradient
          )}>
            <assignment.agent.icon className="h-5 w-5 sm:h-6 sm:w-6" />
          </div>
          {assignment.status === "running" && (
            <motion.div
              className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full bg-blue-500 flex items-center justify-center"
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
                  assignment.confidence >= 90 ? "text-emerald-400" : 
                  assignment.confidence >= 70 ? "text-amber-400" : "text-red-400"
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
                className="ml-auto text-xs font-medium text-violet-400 underline-offset-2 hover:underline"
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
        <div key={index} className="rounded-xl border border-border bg-card/50 p-5">
          <div className="flex items-start gap-4">
            <Skeleton className="h-12 w-12 shrink-0 rounded-xl" />
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

// Stats Card
type StatTrendDirection = "up" | "down" | "neutral"

type AssignmentStat = {
  label: string
  value: number
  icon: IconName
  color: "blue" | "emerald" | "violet" | "amber"
  trend?: { label: string; direction: StatTrendDirection }
  duration?: number
}

function StatTrendBadge({ trend }: { trend: { label: string; direction: StatTrendDirection } }) {
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium sm:text-xs",
        trend.direction === "up" && "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
        trend.direction === "down" && "border-red-500/25 bg-red-500/10 text-red-400",
        trend.direction === "neutral" && "border-border bg-secondary/60 text-muted-foreground",
      )}
    >
      {trend.label}
    </span>
  )
}

function StatCard({ stat, index }: { stat: AssignmentStat; index: number }) {
  const valueColorClass = cn(
    stat.color === "blue" && "text-blue-400",
    stat.color === "emerald" && "text-emerald-400",
    stat.color === "amber" && "text-amber-400",
    stat.color === "violet" && "text-violet-400",
  )

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
      whileHover={{ y: -2, transition: { duration: 0.15 } }}
      className={cn(
        "relative overflow-hidden rounded-2xl border p-5 transition-colors",
        "border-border bg-card/50 hover:bg-secondary/30",
        stat.color === "blue" && stat.value > 0 && "border-blue-500/20",
        stat.color === "violet" && stat.value > 0 && "border-violet-500/20",
      )}
    >
      <div
        className="absolute -top-6 -right-6 h-24 w-24 rounded-full opacity-10"
        style={{
          background:
            stat.color === "blue"
              ? "radial-gradient(circle, #3b82f6 0%, transparent 70%)"
              : stat.color === "emerald"
                ? "radial-gradient(circle, #10b981 0%, transparent 70%)"
                : stat.color === "amber"
                  ? "radial-gradient(circle, #f59e0b 0%, transparent 70%)"
                  : "radial-gradient(circle, #8b5cf6 0%, transparent 70%)",
        }}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div
            className={cn(
              "mb-2 flex h-8 w-8 items-center justify-center rounded-lg sm:mb-3 sm:h-10 sm:w-10 sm:rounded-xl",
              stat.color === "blue" && "bg-blue-500/10",
              stat.color === "emerald" && "bg-emerald-500/10",
              stat.color === "amber" && "bg-amber-500/10",
              stat.color === "violet" && "bg-violet-500/10",
            )}
          >
            <Icon name={stat.icon} size="sm" className={valueColorClass} />
          </div>
          <p className={cn("text-2xl font-bold sm:text-3xl", valueColorClass)}>
            <AnimatedCounter value={stat.value} duration={stat.duration ?? 0.7 + index * 0.1} />
          </p>
          <p className="text-xs text-muted-foreground sm:text-sm">{stat.label}</p>
        </div>
        {stat.trend ? <StatTrendBadge trend={stat.trend} /> : null}
      </div>
    </motion.div>
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
  default: "bg-card border-border/80 shadow-sm",
  blue: "bg-blue-500/10 border-blue-500/25 shadow-sm shadow-blue-500/5",
  violet: "bg-violet-500/10 border-violet-500/25 shadow-sm shadow-violet-500/5",
  emerald: "bg-emerald-500/10 border-emerald-500/25 shadow-sm shadow-emerald-500/5",
  amber: "bg-amber-500/10 border-amber-500/25 shadow-sm shadow-amber-500/5",
  red: "bg-red-500/10 border-red-500/25 shadow-sm shadow-red-500/5",
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
      className="flex items-center gap-1 overflow-x-auto rounded-xl bg-secondary/50 p-1 scrollbar-none"
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
              "relative z-10 flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors sm:gap-2 sm:px-4 sm:py-2 sm:text-sm",
              isActive ? "font-semibold text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {isActive ? (
              <motion.span
                layoutId="assignment-filter-active"
                className={cn("absolute inset-0 rounded-lg border", filterAccentStyles[option.accent])}
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            ) : null}
            <span className="relative z-10 flex items-center gap-1.5">
              {option.showAttentionDot ? (
                <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
                </span>
              ) : null}
              {option.label}
            </span>
            <span
              className={cn(
                "relative z-10 rounded-md px-1 py-0.5 text-[10px] tabular-nums sm:px-1.5 sm:text-xs",
                isActive ? "bg-secondary/80 text-foreground" : "text-muted-foreground",
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

  const stats = useMemo<AssignmentStat[]>(() => {
    const inProgress = assignmentList.filter((a) => a.status === "running").length
    const completed = assignmentList.filter((a) => a.status === "completed").length
    const pendingApproval = assignmentList.filter((a) => a.status === "needs_approval").length
    const queued = assignmentList.filter((a) => a.status === "pending").length

    return [
      {
        label: "In Progress",
        value: inProgress,
        icon: "activity",
        color: "blue",
        trend: { label: "+2 today", direction: "up" },
        duration: 0.6,
      },
      {
        label: "Completed",
        value: completed,
        icon: "check",
        color: "emerald",
        trend: { label: "+5 this week", direction: "up" },
        duration: 0.75,
      },
      {
        label: "Pending Approval",
        value: pendingApproval,
        icon: "clock",
        color: "violet",
        trend: pendingApproval > 0
          ? { label: "Awaiting review", direction: "neutral" }
          : { label: "All clear", direction: "neutral" },
        duration: 0.85,
      },
      {
        label: "Queued",
        value: queued,
        icon: "list",
        color: "amber",
        trend: queued > 0
          ? { label: `${queued} scheduled`, direction: "neutral" }
          : undefined,
        duration: 0.95,
      },
    ]
  }, [assignmentList])

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
    <AppShell title="Assignments">
      <div className="flex flex-col min-h-full">
        {/* Header */}
        <div className="relative overflow-hidden border-b border-border">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-blue-500/5" />
          <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
          
          <div className="relative px-4 sm:px-8 py-4 sm:py-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 sm:mb-6">
              <div className="flex items-center gap-3 sm:gap-4">
                <motion.div 
                  className="h-10 w-10 sm:h-14 sm:w-14 rounded-xl sm:rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center ring-1 ring-emerald-500/20"
                  animate={{ 
                    boxShadow: ["0 0 20px rgba(16, 185, 129, 0.1)", "0 0 40px rgba(16, 185, 129, 0.2)", "0 0 20px rgba(16, 185, 129, 0.1)"]
                  }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Icon name="tasks" size="lg" className="text-emerald-400" />
                </motion.div>
                <div>
                  <div className="flex items-center gap-2 sm:gap-3">
                    <h1 className="text-lg sm:text-2xl font-bold text-foreground">Work Assignments</h1>
                    <ActivityPulse />
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground hidden sm:block">Monitor and manage tasks assigned to your AI team</p>
                </div>
              </div>
              
              <Button 
                className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white border-0 shadow-lg shadow-emerald-500/25 w-full sm:w-auto"
                onClick={openNewAssignment}
              >
                <Icon name="add" size="sm" />
                New Assignment
              </Button>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              {stats.map((stat, i) => (
                <StatCard key={stat.label} stat={stat} index={i} />
              ))}
            </div>
          </div>
        </div>

        {/* Filters & Content */}
        <div className="flex-1 px-4 sm:px-8 py-4 sm:py-6">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-0 mb-4 sm:mb-6">
            <AssignmentFilterTabs options={filterOptions} value={filter} onChange={setFilter} />

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2 h-9">
                <Icon name="filter" size="sm" />
                <span className="hidden sm:inline">Filter</span>
              </Button>
              <div className="flex items-center p-1 rounded-lg bg-secondary/50">
                <button
                  onClick={() => setViewMode("list")}
                  className={cn(
                    "p-2 rounded-md transition-all",
                    viewMode === "list" ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon name="rows" size="sm" />
                </button>
                <button
                  onClick={() => setViewMode("kanban")}
                  className={cn(
                    "p-2 rounded-md transition-all",
                    viewMode === "kanban" ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon name="grid" size="sm" />
                </button>
              </div>
            </div>
          </div>

          {/* Assignment List */}
          {assignmentsError && !showListSkeleton ? (
            <WorkSectionErrorCard
              title="Could not load assignments"
              message="Your assignments list could not be refreshed. Demo data is still available below."
              onRetry={() => void refreshAssignments()}
              className="mb-4"
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
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center py-20"
            >
              <div className="h-20 w-20 rounded-2xl bg-secondary flex items-center justify-center mb-4">
                <Icon name="tasks" size="xl" className="text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {assignmentList.length === 0 ? "No assignments yet" : "No assignments found"}
              </h3>
              <p className="text-sm text-muted-foreground mb-4">
                {assignmentList.length === 0
                  ? "Assign your first task to an AI agent on your team."
                  : "Try adjusting your filters or create a new assignment"}
              </p>
              <Button onClick={openNewAssignment} className="gap-2">
                <Icon name="add" size="sm" />
                New Assignment
              </Button>
            </motion.div>
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
