"use client"

import { useCallback, useMemo, useState, type ReactNode } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { LiveStatus } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { type DemoAssignment } from "@/lib/demo-assignments"
import { ASSIGNMENTS_REFRESH_KEY, fetchAssignmentList } from "@/lib/assignments-list"
import { relativeTime } from "@/lib/agent-job-result"
import { NewAssignmentModal } from "@/components/gravitre/assignments/new-assignment-modal"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { useAuth } from "@/lib/auth-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { LayoutGrid, Rows3 } from "lucide-react"
import { SegmentedControl } from "@/components/gravitre/filter-chip"

type Assignment = DemoAssignment
type Phase = Assignment["status"]

const ASSIGNMENTS_REFRESH_MS = 15_000

/** Execution phases in the order work moves through them; failed is the exception track. */
const PHASES: Array<{ id: Phase; label: string; empty: string }> = [
  { id: "pending", label: "Queued", empty: "Nothing waiting to start." },
  { id: "running", label: "Executing", empty: "No agent is executing work." },
  { id: "needs_approval", label: "Needs your decision", empty: "No decisions waiting." },
  { id: "completed", label: "Delivered", empty: "Nothing delivered yet." },
  { id: "failed", label: "Blocked", empty: "Nothing blocked." },
]

const PHASE_DOT: Record<Phase, string> = {
  pending: "bg-muted-foreground/50",
  running: "bg-[color:var(--g-brand)]",
  needs_approval: "bg-warning",
  completed: "bg-[color:var(--g-text-primary)]",
  failed: "bg-destructive",
}

const PHASE_WASH: Partial<Record<Phase, string>> = {
  needs_approval: "bg-warning/[0.045]",
  failed: "bg-destructive/[0.035]",
}

/** Populated decision/blocked phases get the most room; empty phases compress. */
function phaseColumnTemplate(byPhase: Map<Phase, Assignment[]>): string {
  return PHASES.map((phase) => {
    const n = byPhase.get(phase.id)?.length ?? 0
    if (n === 0) return "minmax(132px,0.55fr)"
    if (phase.id === "needs_approval" || phase.id === "failed") return "minmax(208px,1.25fr)"
    return "minmax(184px,1fr)"
  }).join(" ")
}

const VIEW_MODES = [
  { id: "track" as const, label: "Track view", icon: LayoutGrid },
  { id: "list" as const, label: "List view", icon: Rows3 },
] as const

function phaseLabel(status: Phase): string {
  return PHASES.find((phase) => phase.id === status)?.label ?? status
}

function reportedProgress(assignment: Assignment): number | null {
  if (assignment.status !== "running") return null
  return Number.isFinite(assignment.progress) ? Math.max(0, Math.min(100, assignment.progress)) : null
}

function evidenceLine(assignment: Assignment): string | null {
  const e = assignment.evidence
  if (!e) return null
  const parts: string[] = []
  if (e.toolCalls !== null) parts.push(`${e.toolCalls} tool call${e.toolCalls === 1 ? "" : "s"}`)
  if (e.sources !== null && e.sources > 0) parts.push(`${e.sources} source${e.sources === 1 ? "" : "s"}`)
  if (e.mode === "advisory_only") parts.push("advisory only")
  if (e.mode === "degraded") parts.push("degraded run")
  if (e.verified === true) parts.push("execution verified")
  return parts.length > 0 ? parts.join(" · ") : null
}

function AgentMark({ name }: { name: string }) {
  return (
    <span
      aria-hidden
      className="flex size-5 shrink-0 items-center justify-center rounded-[4px] border border-[color:var(--g-border-default)] text-[10px] font-semibold text-foreground"
    >
      {name.trim().charAt(0).toUpperCase() || "A"}
    </span>
  )
}

/** Execute → Deliver (→ Decision) as a compact step track from the job's own steps. */
function StepTrack({ assignment }: { assignment: Assignment }) {
  const steps = [...assignment.steps]
  if (assignment.status === "needs_approval") steps.push({ name: "Decision", status: "running" })
  return (
    <ol className="flex items-center gap-1" aria-label="Execution steps">
      {steps.map((step) => (
        <li key={step.name} className="flex min-w-0 flex-1 flex-col gap-1">
          <span
            className={cn(
              "h-[3px] w-full",
              step.status === "done" && "bg-[color:var(--g-text-primary)]",
              step.status === "running" &&
                (assignment.status === "needs_approval" && step.name === "Decision" ? "bg-warning" : "bg-[color:var(--g-brand)]"),
              step.status === "pending" && "bg-[color:var(--g-border-default)]",
              assignment.status === "failed" && step.status !== "done" && "bg-destructive/60",
            )}
          />
          <span className="truncate text-[10.5px] text-muted-foreground">
            {step.name}
            <span className="sr-only">: {step.status}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}

function MissionItem({
  assignment,
  selected,
  onActivate,
}: {
  assignment: Assignment
  selected: boolean
  onActivate: () => void
}) {
  const progress = reportedProgress(assignment)
  const evidence = evidenceLine(assignment)
  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        aria-label={`${assignment.title} — ${phaseLabel(assignment.status)}`}
        data-assignment-id={assignment.id}
        onClick={onActivate}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            onActivate()
          }
        }}
        className={cn(
          "group relative flex cursor-pointer flex-col gap-2 rounded-[6px] bg-background px-3 py-2.5 shadow-[0_0_0_1px_var(--g-border-subtle)] transition-shadow hover:shadow-[0_0_0_1px_var(--g-border-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          selected && "shadow-[0_0_0_1.5px_var(--g-text-primary)] hover:shadow-[0_0_0_1.5px_var(--g-text-primary)]",
        )}
      >
        <p className="line-clamp-2 text-[13px] font-semibold leading-snug text-foreground">{assignment.title}</p>
        <div className="flex min-w-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <AgentMark name={assignment.agent.name} />
          <span className="truncate">{assignment.agent.name}</span>
          {assignment.createdAt ? (
            <>
              <span aria-hidden>·</span>
              <span className="shrink-0 tabular-nums">{relativeTime(assignment.createdAt)}</span>
            </>
          ) : null}
        </div>
        <StepTrack assignment={assignment} />
        {assignment.status === "running" && (assignment.currentStepDetail || progress !== null) ? (
          <p className="flex items-start gap-1.5 text-[11.5px] text-foreground">
            <span aria-hidden className="relative mt-1 flex size-1.5 shrink-0">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-[color:var(--g-brand)] opacity-60 motion-reduce:animate-none" />
              <span className="relative inline-flex size-1.5 rounded-full bg-[color:var(--g-brand)]" />
            </span>
            <span>
              {assignment.currentStepDetail?.trim()}
              {progress !== null ? (
                <span className="ml-1 tabular-nums text-muted-foreground">{progress}% reported</span>
              ) : null}
            </span>
          </p>
        ) : null}
        {assignment.status === "needs_approval" ? (
          <div className="rounded-[4px] border-l-[3px] border-warning bg-warning/10 px-2 py-1.5">
            <p className="line-clamp-3 text-[11.5px] text-foreground">
              {assignment.approvalPrompt ?? "The agent paused for your decision before continuing."}
            </p>
            <Link
              href={`/assignments/${assignment.id}?approval=1`}
              onClick={(event) => event.stopPropagation()}
              className="mt-1 inline-flex text-[11.5px] font-semibold text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Decide →
            </Link>
          </div>
        ) : null}
        {assignment.status === "failed" ? (
          <div className="rounded-[4px] border-l-[3px] border-destructive bg-destructive/[0.07] px-2 py-1.5">
            <p className="line-clamp-3 text-[11.5px] text-foreground">
              {assignment.blocker ?? "The job stopped without reporting a reason."}
            </p>
          </div>
        ) : null}
        {assignment.status === "completed" && assignment.resultSummary ? (
          <p className="line-clamp-2 text-[11.5px] text-foreground">
            <span className="font-medium">Result · </span>
            {assignment.resultSummary}
          </p>
        ) : null}
        {evidence ? <p className="text-[11px] text-muted-foreground">{evidence}</p> : null}
      </div>
    </li>
  )
}

function PhaseLane({
  phase,
  items,
  selectedId,
  onActivate,
}: {
  phase: (typeof PHASES)[number]
  items: Assignment[]
  selectedId: string | null
  onActivate: (assignment: Assignment) => void
}) {
  const populated = items.length > 0
  return (
    <section
      aria-labelledby={`phase-${phase.id}`}
      data-assignment-phase={phase.id}
      className={cn(
        "relative flex min-h-0 min-w-0 flex-col",
        populated && PHASE_WASH[phase.id],
      )}
    >
      <span aria-hidden className={cn("absolute inset-x-0 top-0 h-[2px]", populated ? PHASE_DOT[phase.id] : "bg-transparent")} />
      <header className="flex items-center justify-between gap-2 px-3 pb-2 pt-3">
        <h2 id={`phase-${phase.id}`} className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
          <span aria-hidden className={cn("size-1.5 rounded-full", PHASE_DOT[phase.id])} />
          {phase.label}
        </h2>
        <span className={cn("text-[12px] font-semibold tabular-nums", populated ? "text-foreground" : "text-muted-foreground")}>
          {items.length}
        </span>
      </header>
      {items.length === 0 ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">{phase.empty}</p>
      ) : (
        <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 pb-3 pt-0.5">
          {items.map((assignment) => (
            <MissionItem
              key={assignment.id}
              assignment={assignment}
              selected={assignment.id === selectedId}
              onActivate={() => onActivate(assignment)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

/** Selected assignment read as objective → plan → agent → execution → evidence. */
function MissionInspector({ assignment }: { assignment: Assignment | null }) {
  if (!assignment) {
    return (
      <div className="px-4 py-4">
        <p className="text-[13px] font-medium text-foreground">Select an assignment</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Its objective, plan, agent, execution state and evidence appear here.
        </p>
      </div>
    )
  }
  const evidence = evidenceLine(assignment)
  const progress = reportedProgress(assignment)
  const rows: Array<{ label: string; body: ReactNode }> = [
    { label: "Objective", body: <p className="text-[13px] leading-relaxed text-foreground">{assignment.brief}</p> },
    {
      label: "Plan",
      body: (
        <ol className="space-y-1">
          {assignment.steps.map((step) => (
            <li key={step.name} className="flex items-center justify-between gap-2 text-[12.5px]">
              <span className="text-foreground">{step.name}</span>
              <span className="text-muted-foreground">{step.status === "done" ? "Done" : step.status === "running" ? "In progress" : "Not started"}</span>
            </li>
          ))}
        </ol>
      ),
    },
    {
      label: "Agent",
      body: (
        <span className="flex items-center gap-2 text-[12.5px] text-foreground">
          <AgentMark name={assignment.agent.name} />
          {assignment.agent.name}
        </span>
      ),
    },
    {
      label: "Execution",
      body: (
        <div className="space-y-1 text-[12.5px]">
          <p className="flex items-center gap-2 text-foreground">
            <span aria-hidden className={cn("size-1.5 rounded-full", PHASE_DOT[assignment.status])} />
            {phaseLabel(assignment.status)}
            {progress !== null ? <span className="tabular-nums text-muted-foreground">· {progress}% reported</span> : null}
          </p>
          {assignment.currentStepDetail ? <p className="text-muted-foreground">{assignment.currentStepDetail}</p> : null}
          {assignment.status === "needs_approval" && assignment.approvalPrompt ? (
            <p className="text-foreground">{assignment.approvalPrompt}</p>
          ) : null}
          {assignment.blocker ? <p className="text-destructive">{assignment.blocker}</p> : null}
        </div>
      ),
    },
    ...(assignment.resultSummary
      ? [{ label: "Result", body: <p className="text-[12.5px] leading-relaxed text-foreground">{assignment.resultSummary}</p> }]
      : []),
    {
      label: "Evidence",
      body: <p className="text-[12.5px] text-muted-foreground">{evidence ?? "No execution evidence reported for this job."}</p>,
    },
  ]
  return (
    <div className="flex min-h-0 flex-col">
      <div className="border-b border-[color:var(--g-border-subtle)] px-4 py-3">
        <p className="line-clamp-3 text-[14px] font-semibold leading-snug text-foreground">{assignment.title}</p>
        <p className="mt-1 text-[11.5px] text-muted-foreground">
          {assignment.createdAt ? `Created ${relativeTime(assignment.createdAt)}` : null}
          {assignment.completedAt ? ` · finished ${relativeTime(assignment.completedAt)}` : null}
        </p>
      </div>
      <dl className="min-h-0 flex-1 divide-y divide-[color:var(--g-border-subtle)] overflow-y-auto">
        {rows.map((row) => (
          <div key={row.label} className="px-4 py-3">
            <dt className="mb-1.5 text-[11.5px] font-medium text-muted-foreground">{row.label}</dt>
            <dd>{row.body}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2 border-t border-[color:var(--g-border-subtle)] px-4 py-3">
        {assignment.status === "needs_approval" ? (
          <Button size="sm" asChild>
            <Link href={`/assignments/${assignment.id}?approval=1`}>Decide</Link>
          </Button>
        ) : null}
        <Button size="sm" variant={assignment.status === "needs_approval" ? "outline" : "default"} asChild>
          <Link href={`/assignments/${assignment.id}`}>Open assignment</Link>
        </Button>
      </div>
    </div>
  )
}

function MissionListRow({ assignment, onOpen }: { assignment: Assignment; onOpen: () => void }) {
  const evidence = evidenceLine(assignment)
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="grid w-full grid-cols-1 gap-1 px-[var(--np-page-pad-sm)] py-3 text-left transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-[var(--np-page-pad)] md:grid-cols-[minmax(0,1fr)_160px_150px_110px] md:items-center md:gap-4"
      >
        <span className="min-w-0">
          <span className="line-clamp-1 text-[13px] font-medium text-foreground">{assignment.title}</span>
          {assignment.status === "failed" && assignment.blocker ? (
            <span className="line-clamp-1 text-[11.5px] text-destructive">{assignment.blocker}</span>
          ) : assignment.status === "needs_approval" ? (
            <span className="line-clamp-1 text-[11.5px] text-foreground">
              {assignment.approvalPrompt ?? "Waiting for your decision"}
            </span>
          ) : evidence ? (
            <span className="line-clamp-1 text-[11.5px] text-muted-foreground">{evidence}</span>
          ) : null}
        </span>
        <span className="flex min-w-0 items-center gap-1.5 text-[12px] text-muted-foreground">
          <AgentMark name={assignment.agent.name} />
          <span className="truncate">{assignment.agent.name}</span>
        </span>
        <span className="flex items-center gap-1.5 text-[12px] text-foreground">
          <span aria-hidden className={cn("size-1.5 rounded-full", PHASE_DOT[assignment.status])} />
          {phaseLabel(assignment.status)}
        </span>
        <span className="text-[12px] tabular-nums text-muted-foreground md:text-right">
          {assignment.createdAt ? relativeTime(assignment.createdAt) : ""}
        </span>
      </button>
    </li>
  )
}

function TrackSkeleton() {
  return (
    <div className="grid flex-1 grid-cols-1 divide-x divide-[color:var(--g-border-subtle)] md:grid-cols-5">
      {Array.from({ length: 5 }).map((_, index) => (
        <div key={index} className="space-y-3 p-3">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-16 w-full rounded-[var(--np-radius-sm)]" />
          <Skeleton className="h-16 w-full rounded-[var(--np-radius-sm)]" />
        </div>
      ))}
    </div>
  )
}

export default function AssignmentsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [localAssignments, setLocalAssignments] = useState<Assignment[]>([])
  const [viewMode, setViewMode] = useState<"track" | "list">("track")
  const [mobilePhase, setMobilePhase] = useState<Phase | "all">("all")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [newAssignmentOpen, setNewAssignmentOpen] = useState(false)

  const {
    data: fetchedAssignments,
    error: assignmentsError,
    isLoading: assignmentsLoading,
    mutate: refreshAssignments,
  } = useSWR<DemoAssignment[]>(user ? ASSIGNMENTS_REFRESH_KEY : null, fetchAssignmentList, {
    revalidateOnFocus: true,
    refreshInterval: ASSIGNMENTS_REFRESH_MS,
  })

  const assignmentList = useMemo(() => {
    const base = fetchedAssignments ?? []
    const seen = new Set(base.map((item) => item.id))
    const locals = localAssignments.filter((item) => !seen.has(item.id))
    return [...locals, ...base]
  }, [fetchedAssignments, localAssignments])

  const byPhase = useMemo(() => {
    const groups = new Map<Phase, Assignment[]>(PHASES.map((phase) => [phase.id, []]))
    for (const assignment of assignmentList) groups.get(assignment.status)?.push(assignment)
    return groups
  }, [assignmentList])

  const selected = assignmentList.find((item) => item.id === selectedId) ?? null
  // Until the operator picks one, the inspector shows what most needs them.
  const inspected =
    selected ??
    byPhase.get("needs_approval")?.[0] ??
    byPhase.get("failed")?.[0] ??
    byPhase.get("running")?.[0] ??
    assignmentList[0] ??
    null
  usePublishGravitreAISelection(
    selected ? { kind: "assignment", id: selected.id, label: selected.title } : null,
  )

  const openNewAssignment = useCallback(() => setNewAssignmentOpen(true), [])
  useWorkPageShortcut("new", openNewAssignment)

  const openAssignment = (assignment: Assignment) => router.push(`/assignments/${assignment.id}`)
  const activate = (assignment: Assignment) => {
    // Wide screens inspect in place; narrower screens have no inspector, so open the detail.
    if (typeof window !== "undefined" && window.matchMedia("(min-width: 1280px)").matches) {
      setSelectedId(assignment.id)
      return
    }
    openAssignment(assignment)
  }

  const handleAssignmentCreated = (assignment: DemoAssignment) => {
    setLocalAssignments((current) => [assignment, ...current.filter((item) => item.id !== assignment.id)])
    void refreshAssignments()
  }

  const showSkeleton = Boolean(user) && assignmentsLoading && !fetchedAssignments
  const count = (phase: Phase) => byPhase.get(phase)?.length ?? 0
  const statusParts = [
    `${count("running")} executing`,
    `${count("needs_approval")} waiting on you`,
    count("failed") > 0 ? `${count("failed")} blocked` : null,
    `${count("completed")} delivered`,
  ].filter(Boolean)
  const statusTone = count("needs_approval") > 0 || count("failed") > 0 ? "attention" : count("running") > 0 ? "live" : "idle"
  const mobileList = mobilePhase === "all" ? assignmentList : byPhase.get(mobilePhase) ?? []

  return (
    <AppShell title={SURFACE_COPY.pages.assignments.title} fillViewport>
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        {/* Operating command strip */}
        <div className="flex flex-col gap-3 border-b border-[color:var(--g-border-default)] px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] md:flex-row md:items-center md:gap-6">
          <div className="min-w-0 flex-1">
            <h1 className="text-[20px] font-semibold leading-tight tracking-[-0.02em] text-foreground">
              {SURFACE_COPY.pages.assignments.title}
            </h1>
            <div className="mt-0.5">
              <LiveStatus tone={statusTone}>
                {showSkeleton ? "Loading assignments…" : statusParts.join(" · ")}
              </LiveStatus>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <AskGravitreSummonButton selected={selected ? { kind: "assignment", id: selected.id, label: selected.title } : null} />
            <SegmentedControl
              options={VIEW_MODES}
              value={viewMode}
              onChange={setViewMode}
              ariaLabel="Assignment view mode"
              iconOnly
              className="hidden md:inline-flex"
            />
            <Button className="w-full sm:w-auto" onClick={openNewAssignment}>
              <Icon name="add" size="sm" />
              New assignment
            </Button>
          </div>
        </div>

        {assignmentsError && !showSkeleton ? (
          <div className="px-[var(--np-page-pad-sm)] pt-3 sm:px-[var(--np-page-pad)]">
            <WorkSectionErrorCard
              title="Could not load assignments"
              message="Your assignments list could not be refreshed. Showing the last loaded data if available."
              onRetry={() => void refreshAssignments()}
            />
          </div>
        ) : null}

        {showSkeleton ? (
          <TrackSkeleton />
        ) : (
          <>
            {assignmentList.length === 0 ? (
              <div
                data-assignments-empty=""
                className="flex flex-col gap-2 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-rail-bg)] px-[var(--np-page-pad-sm)] py-3 sm:flex-row sm:items-center sm:justify-between sm:px-[var(--np-page-pad)]"
              >
                <div>
                  <p className="text-[13px] font-medium text-foreground">No assignments yet</p>
                  <p className="text-xs text-muted-foreground">
                    Give an agent an objective. It moves through these phases — queued, executing, your decision, delivered — with its evidence.
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={openNewAssignment}>
                  <Icon name="add" size="sm" />
                  Assign the first objective
                </Button>
              </div>
            ) : null}
            {/* Phones: phase filter + mission list */}
            <div className="flex min-h-0 flex-1 flex-col md:hidden">
              <div role="tablist" aria-label="Filter by phase" className="flex overflow-x-auto border-b border-[color:var(--g-border-subtle)] px-2 scrollbar-none">
                {([{ id: "all" as const, label: "All" }, ...PHASES] as Array<{ id: Phase | "all"; label: string }>).map((phase) => {
                  const n = phase.id === "all" ? assignmentList.length : count(phase.id)
                  return (
                    <button
                      key={phase.id}
                      type="button"
                      role="tab"
                      aria-selected={mobilePhase === phase.id}
                      onClick={() => setMobilePhase(phase.id)}
                      className={cn(
                        "relative shrink-0 px-3 py-2.5 text-[13px] font-medium",
                        mobilePhase === phase.id
                          ? "text-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-[color:var(--g-text-primary)]"
                          : "text-muted-foreground",
                      )}
                    >
                      {phase.label}
                      <span className="ml-1 tabular-nums text-muted-foreground">{n}</span>
                    </button>
                  )
                })}
              </div>
              <ul className="min-h-0 flex-1 divide-y divide-[color:var(--g-border-subtle)] overflow-y-auto pb-24">
                {mobileList.length === 0 ? (
                  <li className="px-4 py-4 text-xs text-muted-foreground">Nothing in this phase.</li>
                ) : (
                  mobileList.map((assignment) => (
                    <MissionListRow key={assignment.id} assignment={assignment} onOpen={() => openAssignment(assignment)} />
                  ))
                )}
              </ul>
            </div>

            {/* Tablet and desktop */}
            <div className="hidden min-h-0 flex-1 md:flex">
              {viewMode === "track" ? (
                <div
                  data-assignments-track=""
                  className="grid min-h-0 min-w-0 flex-1 grid-rows-1 divide-x divide-[color:var(--g-border-subtle)] overflow-x-auto"
                  style={{ gridTemplateColumns: phaseColumnTemplate(byPhase) }}
                >
                  {PHASES.map((phase) => (
                    <PhaseLane
                      key={phase.id}
                      phase={phase}
                      items={byPhase.get(phase.id) ?? []}
                      selectedId={inspected?.id ?? null}
                      onActivate={activate}
                    />
                  ))}
                </div>
              ) : (
                <div className="min-h-0 min-w-0 flex-1 overflow-y-auto">
                  <div className="sticky top-0 z-10 hidden grid-cols-[minmax(0,1fr)_160px_150px_110px] gap-4 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] px-[var(--np-page-pad)] py-2 text-[11.5px] font-medium text-muted-foreground md:grid">
                    <span>Objective</span>
                    <span>Agent</span>
                    <span>Phase</span>
                    <span className="text-right">Created</span>
                  </div>
                  <ul className="divide-y divide-[color:var(--g-border-subtle)] pb-24">
                    {assignmentList.map((assignment) => (
                      <MissionListRow key={assignment.id} assignment={assignment} onOpen={() => activate(assignment)} />
                    ))}
                  </ul>
                </div>
              )}
              <aside
                aria-label="Assignment inspector"
                className="hidden w-[340px] shrink-0 flex-col border-l border-[color:var(--g-border-default)] bg-background xl:flex"
              >
                <MissionInspector assignment={inspected} />
              </aside>
            </div>
          </>
        )}
      </div>

      <NewAssignmentModal open={newAssignmentOpen} onOpenChange={setNewAssignmentOpen} onCreated={handleAssignmentCreated} />
    </AppShell>
  )
}
