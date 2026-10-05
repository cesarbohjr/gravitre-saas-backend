"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { relativeTime } from "@/lib/agent-job-result"
import type { DemoAssignment } from "@/lib/demo-assignments"

type Assignment = DemoAssignment
type Phase = Assignment["status"]

/** Groups ordered by how much they need the operator, not by pipeline position. */
const GROUPS: Array<{ id: Phase; label: string; tone: string }> = [
  { id: "needs_approval", label: "Needs your decision", tone: "bg-warning" },
  { id: "failed", label: "Blocked", tone: "bg-destructive" },
  { id: "running", label: "Executing", tone: "bg-[color:var(--g-brand)]" },
  { id: "pending", label: "Queued", tone: "bg-muted-foreground/50" },
  { id: "completed", label: "Completed", tone: "bg-[color:var(--g-text-primary)]" },
]

function timing(assignment: Assignment): string | null {
  if (assignment.status === "completed" && assignment.completedAt) return `Finished ${relativeTime(assignment.completedAt)}`
  if (!assignment.createdAt) return null
  if (assignment.status === "running") return `Started ${relativeTime(assignment.createdAt)}`
  return `Created ${relativeTime(assignment.createdAt)}`
}

/** The single next action each state honestly supports through existing routes. */
function nextAction(assignment: Assignment): { label: string; href: string; emphasis: boolean } {
  const base = `/assignments/${assignment.id}`
  switch (assignment.status) {
    case "needs_approval":
      return { label: "Decide", href: `${base}?approval=1`, emphasis: true }
    case "failed":
      return { label: "See why", href: base, emphasis: false }
    case "completed":
      return { label: "Review result", href: base, emphasis: false }
    case "running":
      return { label: "Follow", href: base, emphasis: false }
    default:
      return { label: "Open", href: base, emphasis: false }
  }
}

function contextLine(assignment: Assignment): { text: string; tone: "warning" | "danger" | "muted" } | null {
  if (assignment.status === "needs_approval") {
    return { text: assignment.approvalPrompt ?? "Paused before continuing. Your decision is required.", tone: "warning" }
  }
  if (assignment.status === "failed") {
    return { text: assignment.blocker ?? "Stopped without reporting a reason.", tone: "danger" }
  }
  if (assignment.status === "running" && assignment.currentStepDetail?.trim()) {
    return { text: assignment.currentStepDetail.trim(), tone: "muted" }
  }
  if (assignment.status === "completed" && assignment.resultSummary) {
    return { text: assignment.resultSummary, tone: "muted" }
  }
  return null
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

function QueueRow({
  assignment,
  selected,
  onActivate,
}: {
  assignment: Assignment
  selected: boolean
  onActivate: () => void
}) {
  const action = nextAction(assignment)
  const context = contextLine(assignment)
  const when = timing(assignment)
  return (
    <li
      data-assignment-id={assignment.id}
      className={cn(
        "group relative grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-[var(--np-page-pad-sm)] py-3 transition-colors hover:bg-[color:var(--g-surface-1)] sm:px-[var(--np-page-pad)] lg:grid-cols-[minmax(0,1fr)_180px_120px_auto]",
        selected && "bg-[color:var(--g-surface-1)]",
      )}
    >
      {selected ? <span aria-hidden className="absolute inset-y-0 left-0 w-[2px] bg-[color:var(--g-text-primary)]" /> : null}
      <button
        type="button"
        onClick={onActivate}
        aria-current={selected ? "true" : undefined}
        className="min-w-0 text-left after:absolute after:inset-0 focus-visible:outline-none [&:focus-visible]:after:ring-2 [&:focus-visible]:after:ring-inset [&:focus-visible]:after:ring-ring"
      >
        <span className="line-clamp-1 text-[14px] font-medium leading-snug text-foreground">{assignment.title}</span>
        {context ? (
          <span
            className={cn(
              "mt-0.5 line-clamp-1 text-[13px] leading-snug",
              context.tone === "warning" && "text-foreground",
              context.tone === "danger" && "text-destructive",
              context.tone === "muted" && "text-muted-foreground",
            )}
          >
            {context.text}
          </span>
        ) : null}
        <span className="mt-1 flex items-center gap-1.5 text-[12px] text-muted-foreground lg:hidden">
          <span className="truncate">{assignment.agent.name}</span>
          {when ? (
            <>
              <span aria-hidden>·</span>
              <span className="shrink-0 tabular-nums">{when}</span>
            </>
          ) : null}
        </span>
      </button>
      <span className="hidden min-w-0 items-center gap-2 text-[13px] text-muted-foreground lg:flex">
        <AgentMark name={assignment.agent.name} />
        <span className="truncate">{assignment.agent.name}</span>
      </span>
      <span className="hidden text-[12px] tabular-nums text-muted-foreground lg:block">{when ?? ""}</span>
      <Link
        href={action.href}
        className={cn(
          "relative z-10 inline-flex h-7 shrink-0 items-center rounded-[6px] px-2.5 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          action.emphasis
            ? "bg-primary text-primary-foreground hover:bg-primary/90"
            : "text-foreground shadow-[0_0_0_1px_var(--g-border-default)] hover:shadow-[0_0_0_1px_var(--g-border-strong)]",
        )}
      >
        {action.label}
        <span className="sr-only">: {assignment.title}</span>
      </Link>
    </li>
  )
}

export function AssignmentQueue({
  assignments,
  selectedId,
  onActivate,
}: {
  assignments: Assignment[]
  selectedId: string | null
  onActivate: (assignment: Assignment) => void
}) {
  const groups = GROUPS.map((group) => ({
    ...group,
    items: assignments.filter((assignment) => assignment.status === group.id),
  }))
  const populated = groups.filter((group) => group.items.length > 0)
  const empty = groups.filter((group) => group.items.length === 0)

  return (
    <div data-assignments-queue="" className="min-h-0 min-w-0 flex-1 overflow-y-auto pb-24">
      {populated.map((group) => (
        <section key={group.id} aria-labelledby={`queue-${group.id}`} data-assignment-phase={group.id}>
          <h2
            id={`queue-${group.id}`}
            className="sticky top-0 z-20 flex items-center gap-2 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] py-2 text-[13px] font-semibold text-foreground sm:px-[var(--np-page-pad)]"
          >
            <span aria-hidden className={cn("size-1.5 rounded-full", group.tone)} />
            {group.label}
            <span className="font-normal tabular-nums text-muted-foreground">{group.items.length}</span>
          </h2>
          <ul className="divide-y divide-[color:var(--g-border-subtle)] border-b border-[color:var(--g-border-subtle)]">
            {group.items.map((assignment) => (
              <QueueRow
                key={assignment.id}
                assignment={assignment}
                selected={assignment.id === selectedId}
                onActivate={() => onActivate(assignment)}
              />
            ))}
          </ul>
        </section>
      ))}
      {populated.length > 0 && empty.length > 0 ? (
        <p className="px-[var(--np-page-pad-sm)] py-3 text-[12px] text-muted-foreground sm:px-[var(--np-page-pad)]">
          {"Nothing "}
          {empty.map((group) => group.label.toLowerCase()).join(", ")}
          {"."}
        </p>
      ) : null}
    </div>
  )
}
