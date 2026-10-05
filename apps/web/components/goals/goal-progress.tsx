import { Check } from "lucide-react"

import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export type GoalMilestone = { id: string; title: string; status?: string }

type MilestoneState = "done" | "active" | "pending"

function milestoneState(status?: string): MilestoneState {
  if (status === "completed") return "done"
  if (status === "in_progress") return "active"
  return "pending"
}

export function GoalProgressSummary({ progress, milestones }: { progress: number | null; milestones: GoalMilestone[] | null }) {
  const list = milestones ?? []
  const done = list.filter((milestone) => milestoneState(milestone.status) === "done").length
  const active = list.find((milestone) => milestoneState(milestone.status) === "active")

  return (
    <section aria-labelledby="goal-progress-heading" className="flex flex-col gap-5 border-y border-divide py-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="goal-progress-heading" className={TYPE.eyebrow}>Goal progress</h2>
          <p className="text-sm text-muted-foreground">
            {list.length ? `${done} of ${list.length} milestones complete` : progress == null ? "No progress measurement was returned for this goal." : "Progress reported by the goal service."}
          </p>
        </div>
        <p className="font-sans text-4xl font-medium tabular-nums leading-none text-[color:var(--g-text-primary)]">
          {progress == null ? <span className="text-xl text-muted-foreground">Not reported</span> : <>{progress}<span className="text-xl text-muted-foreground">%</span></>}
        </p>
      </div>

      {list.length ? (
        <div
          role="progressbar"
          aria-label="Goal progress"
          aria-valuenow={progress ?? undefined}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuetext={`${done} of ${list.length} milestones complete`}
          className="flex gap-1"
        >
          {list.map((milestone) => {
            const state = milestoneState(milestone.status)
            return (
              <span
                key={milestone.id}
                title={milestone.title}
                className={cn(
                  "relative h-2 flex-1 overflow-hidden rounded-full",
                  state === "done" && "bg-[color:var(--g-brand)]",
                  state === "active" && "bg-secondary",
                  state === "pending" && "bg-secondary",
                )}
              >
                {state === "active" ? <span className="absolute inset-y-0 left-0 w-1/2 rounded-full bg-[color:var(--g-electric)] motion-safe:animate-pulse" /> : null}
              </span>
            )
          })}
        </div>
      ) : progress != null ? (
        <div role="progressbar" aria-label="Goal progress" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-secondary">
          <div className="h-full rounded-full bg-[color:var(--g-brand)]" style={{ width: `${progress}%` }} />
        </div>
      ) : null}

      {active ? (
        <div className="flex items-start gap-3 rounded-md border border-[color:var(--g-electric)]/30 bg-[color:var(--g-electric)]/5 px-3 py-2.5">
          <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-full bg-[color:var(--g-electric)] motion-safe:animate-pulse" />
          <p className="min-w-0 text-sm leading-6 text-pretty">
            <span className="text-muted-foreground">In progress now: </span>
            <span className="font-medium text-foreground">{active.title}</span>
          </p>
        </div>
      ) : null}
    </section>
  )
}

export function MilestoneTrack({ milestones }: { milestones: GoalMilestone[] }) {
  return (
    <ol className="mt-4 flex flex-col">
      {milestones.map((milestone, index) => {
        const state = milestoneState(milestone.status)
        const isLast = index === milestones.length - 1
        return (
          <li key={milestone.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast ? (
              <span
                aria-hidden
                className={cn("absolute left-[11px] top-7 bottom-1 w-px", state === "done" ? "bg-[color:var(--g-brand)]" : "bg-divide")}
              />
            ) : null}
            <span
              aria-hidden
              className={cn(
                "relative z-10 mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-medium tabular-nums",
                state === "done" && "border-[color:var(--g-brand)] bg-[color:var(--g-brand)] text-background",
                state === "active" && "border-[color:var(--g-electric)] bg-background text-[color:var(--g-electric)] ring-4 ring-[color:var(--g-electric)]/15",
                state === "pending" && "border-divide bg-background text-muted-foreground",
              )}
            >
              {state === "done" ? <Check className="size-3.5" strokeWidth={3} /> : index + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1 pt-0.5">
              <p className={cn("break-words text-sm font-medium text-pretty", state === "pending" ? "text-muted-foreground" : "text-foreground")}>
                {milestone.title}
              </p>
              <p className={cn("text-xs", state === "active" ? "text-[color:var(--g-electric)]" : state === "done" ? "text-[color:var(--g-brand-active)]" : "text-muted-foreground")}>
                <span className="sr-only">Status: </span>
                {state === "done" ? "Completed" : state === "active" ? "In progress" : milestone.status && milestone.status !== "pending" ? milestone.status.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase()) : "Not started"}
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
