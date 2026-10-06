"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { relativeTime } from "@/lib/agent-job-result"
import type { DemoAssignment } from "@/lib/demo-assignments"

type Assignment = DemoAssignment
type Phase = Assignment["status"]

/** Sections ordered by how much they need the operator, not by pipeline position. */
const SECTIONS: Array<{ id: Phase; label: string; emptyLabel: string }> = [
  { id: "needs_approval", label: "Your turn", emptyLabel: "nothing waiting on you" },
  { id: "failed", label: "Blocked", emptyLabel: "nothing blocked" },
  { id: "running", label: "At work now", emptyLabel: "no agent working" },
  { id: "pending", label: "Up next", emptyLabel: "nothing queued" },
  { id: "completed", label: "Delivered", emptyLabel: "nothing delivered yet" },
]

const detailHref = (assignment: Assignment) => `/assignments/${assignment.id}`

function plural(count: number, one: string, many: string) {
  return `${count} ${count === 1 ? one : many}`
}

/** One honest sentence about the queue, built only from counts the list already has. */
export function queueBriefing(assignments: Assignment[]): { lead: string; rest: string | null } {
  const count = (phase: Phase) => assignments.filter((item) => item.status === phase).length
  const decisions = count("needs_approval")
  const blocked = count("failed")
  const working = count("running")
  const queued = count("pending")

  const lead =
    decisions > 0
      ? `${plural(decisions, "decision is", "decisions are")} waiting on you.`
      : blocked > 0
        ? `${plural(blocked, "assignment is", "assignments are")} blocked.`
        : working > 0
          ? "Nothing needs you right now."
          : "All quiet."

  const parts: string[] = []
  if (decisions > 0 && blocked > 0) parts.push(`${blocked} blocked`)
  if (working > 0) parts.push(`${plural(working, "agent", "agents")} at work`)
  if (queued > 0) parts.push(`${queued} up next`)
  return { lead, rest: parts.length > 0 ? `${parts.join(", ")}.` : null }
}

function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])
  return now
}

function elapsedSince(iso: string | undefined, now: number): string | null {
  if (!iso) return null
  const started = new Date(iso).getTime()
  if (Number.isNaN(started)) return null
  const seconds = Math.max(0, Math.floor((now - started) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`
}

/** The agent's working identity: its role icon on a quiet tile, so agents are recognisable at a glance. */
function AgentTile({ assignment, live = false }: { assignment: Assignment; live?: boolean }) {
  const Icon = assignment.agent.icon
  return (
    <span
      aria-hidden
      className={cn(
        "relative flex size-9 shrink-0 items-center justify-center rounded-lg border",
        live
          ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-emerald-surface)] text-[color:var(--g-brand)]"
          : "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] text-foreground",
      )}
    >
      <Icon className="size-4" strokeWidth={1.75} />
      {live ? (
        <span className="absolute -right-0.5 -top-0.5 flex size-2.5">
          <span className="g-live-ping absolute inline-flex size-full rounded-full bg-[color:var(--g-brand)] opacity-60" />
          <span className="relative inline-flex size-2.5 rounded-full border-2 border-[color:var(--g-canvas)] bg-[color:var(--g-brand)]" />
        </span>
      ) : null}
    </span>
  )
}

function SectionHeading({ id, label, count }: { id: string; label: string; count: number }) {
  return (
    <h2 id={id} className="flex items-baseline gap-2 text-[15px] font-semibold text-foreground">
      {label}
      <span className="text-[13px] font-normal tabular-nums text-muted-foreground">{count}</span>
    </h2>
  )
}

/** A paused governed action, presented where the operator can decide what to do with it. */
function DecisionCard({ assignment }: { assignment: Assignment }) {
  const ask = assignment.approvalPrompt ?? "Paused before continuing. Your decision is required."
  return (
    <li
      data-assignment-id={assignment.id}
      className="flex flex-col gap-3 rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4"
    >
      <div className="flex items-center gap-3">
        <AgentTile assignment={assignment} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium text-foreground">{assignment.agent.name}</p>
          <p className="text-[13px] text-muted-foreground">
            {"Paused "}
            {relativeTime(assignment.completedAt ?? assignment.createdAt)}
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-warning/15 px-2 py-0.5 text-[12px] font-medium text-foreground">
          <span aria-hidden className="size-1.5 rounded-full bg-warning" />
          Needs you
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="text-pretty text-[15px] font-semibold leading-snug text-foreground">{assignment.title}</h3>
        <p className="text-pretty text-[14px] leading-relaxed text-foreground/90">{ask}</p>
        {assignment.resultSummary ? (
          <p className="line-clamp-2 text-[14px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground/80">{"Found: "}</span>
            {assignment.resultSummary}
          </p>
        ) : null}
      </div>

      <div className="flex gap-2">
        <Link
          href={`${detailHref(assignment)}?approval=1`}
          className="inline-flex h-11 flex-1 items-center justify-center rounded-lg bg-primary px-4 text-[14px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex-none"
        >
          Review and decide
          <span className="sr-only">: {assignment.title}</span>
        </Link>
        <Link
          href={detailHref(assignment)}
          className="inline-flex h-11 items-center justify-center rounded-lg px-4 text-[14px] font-medium text-foreground shadow-[0_0_0_1px_var(--g-border-default)] transition-shadow hover:shadow-[0_0_0_1px_var(--g-border-strong)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Open
          <span className="sr-only">: {assignment.title}</span>
        </Link>
      </div>
    </li>
  )
}

/** Reported progress fills the trace; unreported progress scans instead of inventing a number. */
function Trace({ progress }: { progress: number }) {
  const known = Number.isFinite(progress)
  return (
    <div
      role="progressbar"
      aria-label="Progress"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? progress : undefined}
      aria-valuetext={known ? `${progress}%` : "Progress not reported"}
      className="relative h-1 w-full overflow-hidden rounded-full bg-[color:var(--g-border-subtle)]"
    >
      {known ? (
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-[color:var(--g-brand)] transition-[width] duration-700"
          style={{ width: `${Math.max(4, Math.min(100, progress))}%` }}
        />
      ) : (
        <span className="g-trace-scan absolute inset-y-0 w-1/3 rounded-full bg-[color:var(--g-brand)]" />
      )}
    </div>
  )
}

/** Signature element: an agent visibly at work, with its real step chain and a live clock. */
function LiveCard({ assignment, now, onActivate }: { assignment: Assignment; now: number; onActivate: () => void }) {
  const elapsed = elapsedSince(assignment.createdAtIso ?? assignment.createdAt, now)
  const current = assignment.steps.find((step) => step.status === "running")
  const doing = assignment.currentStepDetail?.trim() || (current ? `${current.name} step in progress` : "Working")
  const known = Number.isFinite(assignment.progress)
  return (
    <li data-assignment-id={assignment.id} className="relative min-w-0">
      <button
        type="button"
        onClick={onActivate}
        className="flex w-full min-w-0 flex-col gap-3 rounded-xl border border-[color:var(--g-brand-border)] bg-[color:var(--g-canvas)] p-4 text-left transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex w-full min-w-0 items-center gap-3">
          <AgentTile assignment={assignment} live />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[14px] font-medium text-foreground">{assignment.title}</span>
            <span className="block truncate text-[13px] text-muted-foreground">{assignment.agent.name}</span>
          </span>
          {elapsed ? (
            <span className="shrink-0 font-mono text-[13px] tabular-nums text-foreground" aria-label={`Working for ${elapsed}`}>
              {elapsed}
            </span>
          ) : null}
        </span>

        <Trace progress={assignment.progress} />

        <span className="flex w-full min-w-0 items-center justify-between gap-3">
          <span className="min-w-0 truncate text-[14px] text-foreground/90">{doing}</span>
          {known ? (
            <span className="shrink-0 text-[13px] tabular-nums text-muted-foreground">{assignment.progress}%</span>
          ) : null}
        </span>

        {assignment.steps.length > 1 ? (
          <span className="flex flex-wrap items-center gap-1.5" aria-label="Steps">
            {assignment.steps.map((step, index) => (
              <span key={`${step.name}-${index}`} className="flex items-center gap-1.5">
                {index > 0 ? <span aria-hidden className="h-px w-3 bg-[color:var(--g-border-default)]" /> : null}
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px]",
                    step.status === "done" && "text-muted-foreground",
                    step.status === "running" && "bg-[color:var(--g-emerald-surface)] font-medium text-foreground",
                    step.status === "pending" && "text-muted-foreground/70",
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "size-1.5 rounded-full",
                      step.status === "done" && "bg-muted-foreground",
                      step.status === "running" && "bg-[color:var(--g-brand)]",
                      step.status === "pending" && "border border-muted-foreground/60",
                    )}
                  />
                  {step.name}
                  <span className="sr-only">{`, ${step.status}`}</span>
                </span>
              </span>
            ))}
          </span>
        ) : null}
      </button>
    </li>
  )
}

function rowContext(assignment: Assignment): { text: string; tone: "danger" | "muted" } | null {
  if (assignment.status === "failed") return { text: assignment.blocker ?? "Stopped without reporting a reason.", tone: "danger" }
  if (assignment.status === "completed" && assignment.resultSummary) return { text: assignment.resultSummary, tone: "muted" }
  return null
}

function rowTiming(assignment: Assignment): string | null {
  if (assignment.status === "completed" && assignment.completedAt) return relativeTime(assignment.completedAt)
  if (assignment.status === "failed" && assignment.completedAt) return `Stopped ${relativeTime(assignment.completedAt)}`
  if (!assignment.createdAt) return null
  return `Created ${relativeTime(assignment.createdAt)}`
}

const ROW_ACTION: Partial<Record<Phase, string>> = { failed: "See why", completed: "Review", pending: "Open" }

/** Compact rows for work that is waiting or done: the whole row is the touch target. */
function QueueRow({ assignment, selected, onActivate }: { assignment: Assignment; selected: boolean; onActivate: () => void }) {
  const context = rowContext(assignment)
  const when = rowTiming(assignment)
  return (
    <li data-assignment-id={assignment.id} className="relative">
      <button
        type="button"
        onClick={onActivate}
        aria-current={selected ? "true" : undefined}
        className={cn(
          "flex min-h-14 w-full items-center gap-3 px-1 py-3 text-left transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
          selected && "bg-[color:var(--g-surface-1)]",
        )}
      >
        <AgentTile assignment={assignment} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] font-medium text-foreground">{assignment.title}</span>
          {context ? (
            <span
              className={cn(
                "mt-0.5 line-clamp-2 text-[14px] leading-snug",
                context.tone === "danger" ? "text-destructive" : "text-muted-foreground",
              )}
            >
              {context.text}
            </span>
          ) : null}
          <span className="mt-0.5 block truncate text-[13px] text-muted-foreground">
            {assignment.agent.name}
            {when ? ` · ${when}` : ""}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-0.5 text-[13px] font-medium text-muted-foreground">
          <span className="hidden sm:inline">{ROW_ACTION[assignment.status] ?? "Open"}</span>
          <ChevronRight aria-hidden className="size-4" />
        </span>
      </button>
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
  const now = useNow(1000)
  const sections = SECTIONS.map((section) => ({
    ...section,
    items: assignments.filter((assignment) => assignment.status === section.id),
  }))
  const populated = sections.filter((section) => section.items.length > 0)
  const quiet = sections.filter((section) => section.items.length === 0 && section.id !== "completed")
  const briefing = queueBriefing(assignments)

  return (
    <div data-assignments-queue="" className="min-h-0 min-w-0 flex-1 overflow-y-auto pb-24">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-[var(--np-page-pad-sm)] py-5 sm:px-[var(--np-page-pad)]">
        {assignments.length > 0 ? (
          <p data-queue-briefing="" className="text-pretty text-[17px] leading-snug text-foreground">
            <span className="font-semibold">{briefing.lead}</span>
            {briefing.rest ? <span className="text-muted-foreground">{` ${briefing.rest}`}</span> : null}
          </p>
        ) : null}

        {populated.map((section) => {
          const headingId = `queue-${section.id}`
          return (
            <section key={section.id} aria-labelledby={headingId} data-assignment-phase={section.id} className="flex flex-col gap-3">
              <SectionHeading id={headingId} label={section.label} count={section.items.length} />
              {section.id === "needs_approval" ? (
                <ul className="flex flex-col gap-3">
                  {section.items.map((assignment) => (
                    <DecisionCard key={assignment.id} assignment={assignment} />
                  ))}
                </ul>
              ) : section.id === "running" ? (
                <ul className="grid gap-3 lg:grid-cols-2">
                  {section.items.map((assignment) => (
                    <LiveCard key={assignment.id} assignment={assignment} now={now} onActivate={() => onActivate(assignment)} />
                  ))}
                </ul>
              ) : (
                <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
                  {section.items.map((assignment) => (
                    <QueueRow
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
        })}

        {populated.length > 0 && quiet.length > 0 ? (
          <p className="text-[13px] text-muted-foreground">
            {"Also: "}
            {quiet.map((section) => section.emptyLabel).join(", ")}
            {"."}
          </p>
        ) : null}
      </div>
    </div>
  )
}
