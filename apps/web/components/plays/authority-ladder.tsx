import { cn } from "@/lib/utils"

export type AuthorityReadiness = {
  observe_ready?: boolean
  recommend_ready?: boolean
  act_with_approval_ready?: boolean
  act_within_policy_ready?: boolean
  blockers?: string[]
}

const RUNGS = [
  { key: "observe_ready", label: "Observe", short: "Watches your systems" },
  { key: "recommend_ready", label: "Recommend", short: "Suggests next steps" },
  { key: "act_with_approval_ready", label: "Act with approval", short: "Acts after a person approves" },
  { key: "act_within_policy_ready", label: "Act within policy", short: "Acts on its own inside policy" },
] as const

/** How many consecutive rungs, from the bottom, this play has earned. */
export function earnedRungs(readiness: AuthorityReadiness): number {
  let count = 0
  for (const rung of RUNGS) {
    if (!readiness[rung.key]) break
    count += 1
  }
  return count
}

export function AuthorityLadder({ readiness, className }: { readiness: AuthorityReadiness; className?: string }) {
  const earned = earnedRungs(readiness)
  const next = RUNGS[earned]
  const blocker = readiness.blockers?.[0]
  const current = earned > 0 ? RUNGS[earned - 1] : null

  return (
    <div className={cn("flex min-w-0 flex-col gap-2", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Authority</p>
        <p className="text-sm font-medium text-foreground">{current ? current.label : "Not started"}</p>
      </div>
      <ol aria-label={`Authority: ${earned} of ${RUNGS.length} levels earned`} className="grid grid-cols-4 gap-1">
        {RUNGS.map((rung, index) => {
          const state = index < earned ? "earned" : index === earned ? "next" : "locked"
          return (
            <li key={rung.key} title={`${rung.label}: ${rung.short}`} className="flex flex-col gap-1">
              <span
                aria-hidden
                className={cn(
                  "h-1.5 rounded-full",
                  state === "earned" && "bg-[color:var(--g-brand)]",
                  state === "next" && "border border-dashed border-[color:var(--g-brand)] bg-transparent",
                  state === "locked" && "bg-secondary",
                )}
              />
              <span className="sr-only">
                {rung.label}: {state === "earned" ? "earned" : state === "next" ? "next level" : "not yet available"}
              </span>
            </li>
          )
        })}
      </ol>
      <p className="text-xs leading-5 text-muted-foreground text-pretty">
        {blocker
          ? <><span className="text-warning">Blocked:</span> {blocker}</>
          : next
            ? <>Next: <span className="text-foreground">{next.label}</span>. {next.short}.</>
            : "Full authority earned inside your policy."}
      </p>
    </div>
  )
}
