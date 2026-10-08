"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { CheckCircle2, Circle, MoreHorizontal, Sparkles } from "lucide-react"
import { objectivesApi } from "@/lib/api"
import type { DemoAssignment } from "@/lib/demo-assignments"
import type { GoalRecord, GoalStatus } from "@/lib/goals-list"
import {
  GOAL_STATUS_TABS,
  cadenceLabel,
  capitalize,
  departmentLabel,
  formatShortDate,
  goalMeasure,
  goalMetrics,
  goalSetupChecklist,
  goalStatusOf,
  initials,
  relatedWorkSummary,
} from "@/lib/goal-insights"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function statusLabel(status: GoalStatus | "unreported"): string {
  if (status === "unreported") return "Status not reported"
  return GOAL_STATUS_TABS.find((t) => t.id === status)?.label ?? capitalize(status)
}

function formatNumber(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

/** Verified current value for goals that carry an objective contract. */
function useObjectiveCurrent(goal: GoalRecord): number | null {
  const isObjective = goalMetrics(goal).isObjective
  const { data } = useSWR(
    isObjective ? ["goal-objective-progress", goal.id] : null,
    () => objectivesApi.progress(goal.id),
    { revalidateOnFocus: false },
  )
  return typeof data?.current === "number" && Number.isFinite(data.current) ? data.current : null
}

export function GoalCard({
  goal,
  related,
  onContinue,
  onSetStatus,
}: {
  goal: GoalRecord
  related: DemoAssignment | null
  onContinue: (goal: GoalRecord) => void
  onSetStatus: (goal: GoalRecord, status: GoalStatus) => Promise<void>
}) {
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [pending, setPending] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const status = goalStatusOf(goal)
  const reported = useObjectiveCurrent(goal)
  const measure = goalMeasure(goal, reported)
  const checklist = goalSetupChecklist(goal)
  const doneCount = checklist.filter((c) => c.done).length
  const owner = goalMetrics(goal).ownerName
  const dept = departmentLabel(goal.department)
  const created = formatShortDate(goal.createdAt)

  async function setStatus(next: GoalStatus) {
    if (pending) return
    setPending(true)
    setActionError(null)
    try {
      await onSetStatus(goal, next)
      setConfirmCancel(false)
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Could not update this goal. Try again.")
    } finally {
      setPending(false)
    }
  }

  return (
    <article className="gv-card gv-goal gv-rise" aria-labelledby={`goal-${goal.id}-title`}>
      <div className="gv-goal-pills">
        <span className="gv-pill neutral">
          <span className="gv-sdot" data-status={status} aria-hidden />
          {statusLabel(status)}
        </span>
        {dept ? <span className="gv-pill brand">{dept}</span> : null}
        {goal.priority ? (
          <span className="gv-pill outline">{capitalize(goal.priority)} priority</span>
        ) : null}
        {created ? <span className="created">Created {created}</span> : null}
      </div>
      <h3 className="gv-goal-title" id={`goal-${goal.id}-title`}>
        <Link href={`/goals/${goal.id}`}>{goal.objective || "Objective not reported"}</Link>
      </h3>
      <div className="gv-goal-owner">
        {owner ? (
          <span className="gv-goal-ava" aria-hidden>
            {initials(owner)}
          </span>
        ) : null}
        <span>
          {owner ? `Owned by ${owner.split(/\s+/)[0]} · ` : ""}
          {cadenceLabel(goal.frequency)}
        </span>
      </div>

      <div className="gv-goal-blocks">
        <div className="gv-goal-block">
          <div className="gv-eyebrow">Measure</div>
          <div className="gv-goal-measure">
            {measure.current !== null ? (
              <span className="big">{formatNumber(measure.current)}</span>
            ) : (
              <span className="big unreported">
                {status === "draft" ? "No starting value set" : "Current value not reported"}
              </span>
            )}
            {measure.target !== null ? (
              <span className="of">
                of {formatNumber(measure.target)}
                {measure.metric ? ` ${measure.metric}` : ""}
              </span>
            ) : measure.metric ? (
              <span className="of">{measure.metric} · target not set</span>
            ) : (
              <span className="of">Target not set</span>
            )}
          </div>
          <div
            className={cn("gv-goal-bar", measure.percent === null && "unknown")}
            role="progressbar"
            aria-label="Progress toward target"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={measure.percent ?? undefined}
            aria-valuetext={measure.percent === null ? "Not reported" : `${measure.percent}%`}
          >
            <div style={{ width: `${measure.percent ?? 0}%` }} />
          </div>
          <div className="gv-goal-meta">
            <span>{measure.stateLabel}</span>
            <span>{measure.dueLabel}</span>
          </div>
        </div>
        <div className="gv-goal-block">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="gv-eyebrow">Finish setup</span>
            <span className="gv-mono" style={{ fontSize: 12, color: "var(--gv-muted)" }}>
              {doneCount} of {checklist.length}
            </span>
          </div>
          <ul className="gv-goal-check">
            {checklist.map((item) => (
              <li key={item.label} className={item.done ? "done" : undefined}>
                {item.done ? (
                  <CheckCircle2 className="ok size-[18px]" aria-label="Done" />
                ) : (
                  <Circle className="todo size-[18px]" strokeDasharray="3 3" aria-label="Not done" />
                )}
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {related ? (
        <div className="gv-goal-related">
          <span className="gv-goal-spark" aria-hidden>
            <Sparkles className="size-4" />
          </span>
          <div className="body">
            <div style={{ fontWeight: 600 }}>Gravitre found related work</div>
            <div style={{ color: "var(--gv-muted)" }}>{relatedWorkSummary(related)}</div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 }}>
              <Link className="gv-link" href={`/assignments/${related.id}`}>
                Open the assignment →
              </Link>
            </div>
          </div>
        </div>
      ) : null}

      {confirmCancel ? (
        <div className="gv-goal-related" role="alertdialog" aria-label="Cancel this goal" style={{ background: "var(--gv-red-soft)", borderColor: "var(--gv-red-border)" }}>
          <div className="body">
            <div style={{ fontWeight: 600 }}>Cancel this goal?</div>
            <div style={{ color: "var(--gv-muted)" }}>
              It stays in the Cancelled tab with its plan. You can reopen it as a draft later.
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 10 }}>
              <button type="button" className="gv-btn danger sm" disabled={pending} onClick={() => void setStatus("cancelled")}>
                Cancel goal
              </button>
              <button type="button" className="gv-btn plain sm" disabled={pending} onClick={() => setConfirmCancel(false)}>
                Keep goal
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {actionError ? (
        <p role="alert" style={{ margin: "12px 0 0", fontSize: 14, color: "var(--gv-red-text)" }}>
          {actionError}
        </p>
      ) : null}

      <div className="gv-goal-foot">
        {status === "draft" ? (
          <>
            <button type="button" className="gv-btn primary" onClick={() => onContinue(goal)}>
              Continue setup
            </button>
            <Link className="gv-btn ghost" href={`/goals/${goal.id}`}>
              Preview plan
            </Link>
          </>
        ) : (
          <>
            <Link className="gv-btn primary" href={`/goals/${goal.id}`}>
              Open goal
            </Link>
            {status !== "cancelled" ? (
              <button type="button" className="gv-btn ghost" onClick={() => onContinue(goal)}>
                Edit goal
              </button>
            ) : null}
          </>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className="gv-iconbtn more" aria-label="More actions" disabled={pending}>
              <MoreHorizontal className="size-[18px]" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href={`/goals/${goal.id}`}>Open goal details</Link>
            </DropdownMenuItem>
            {status === "active" ? (
              <DropdownMenuItem onSelect={() => void setStatus("paused")}>Pause goal</DropdownMenuItem>
            ) : null}
            {status === "paused" ? (
              <DropdownMenuItem onSelect={() => void setStatus("active")}>Resume goal</DropdownMenuItem>
            ) : null}
            {status === "active" || status === "paused" ? (
              <DropdownMenuItem onSelect={() => void setStatus("completed")}>Mark completed</DropdownMenuItem>
            ) : null}
            {status === "cancelled" || status === "completed" ? (
              <DropdownMenuItem onSelect={() => void setStatus("draft")}>Reopen as draft</DropdownMenuItem>
            ) : null}
            {status === "draft" || status === "active" || status === "paused" ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setConfirmCancel(true)}>Cancel goal</DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </article>
  )
}

export function GoalBoardCard({ goal }: { goal: GoalRecord }) {
  const reported = useObjectiveCurrent(goal)
  const measure = goalMeasure(goal, reported)
  const dept = departmentLabel(goal.department)
  return (
    <Link href={`/goals/${goal.id}`} className="gv-card gv-board-card">
      <div className="t">{goal.objective || "Objective not reported"}</div>
      <div className="s">
        {[dept, goal.priority ? `${capitalize(goal.priority)} priority` : null, measure.dueLabel]
          .filter(Boolean)
          .join(" · ")}
      </div>
      {measure.percent !== null ? (
        <div className="gv-goal-bar" style={{ marginTop: 10, height: 6 }} aria-hidden>
          <div style={{ width: `${measure.percent}%` }} />
        </div>
      ) : null}
    </Link>
  )
}
