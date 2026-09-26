"use client"

import type { ReactNode } from "react"
import { NucleoActivity, NucleoApproval, NucleoError, NucleoHistory, NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { AI_RUNTIME_STATE_COPY, type AiRuntimeState } from "@/lib/gravitre-ai-runtime-state"

const TONE: Record<AiRuntimeState, string> = {
  idle: "text-[color:var(--g-text-muted)]",
  streaming: "text-[color:var(--g-intelligence)]",
  generating: "text-[color:var(--g-intelligence)]",
  completed: "text-[color:var(--g-success)]",
  needs_approval: "text-[color:var(--g-warning)]",
  blocked: "text-[color:var(--g-warning)]",
  failed: "text-[color:var(--g-danger)]",
  partial: "text-[color:var(--g-warning)]",
  resumed: "text-[color:var(--g-intelligence)]",
}

function StateIcon({ state }: { state: AiRuntimeState }) {
  const cls = "h-3.5 w-3.5 shrink-0"
  switch (state) {
    case "completed":
      return <NucleoSuccess className={cls} aria-hidden />
    case "failed":
      return <NucleoError className={cls} aria-hidden />
    case "needs_approval":
    case "blocked":
      return <NucleoApproval className={cls} aria-hidden />
    case "partial":
    case "resumed":
      return <NucleoHistory className={cls} aria-hidden />
    default:
      return <NucleoActivity className={cls} aria-hidden />
  }
}

/**
 * One-line runtime truth for the AI workspace. Idle renders nothing: the absence
 * of a status line is the idle state. Live states (streaming, generating) pulse
 * only under `motion-safe`, and only while the runtime reports them.
 */
export function GravitreAIRuntimeStatus({
  state,
  fixture = false,
  action,
  className,
}: {
  state: AiRuntimeState
  /** Dev previews only — adds an explicit FIXTURE marker so it cannot read as production. */
  fixture?: boolean
  /** Trailing control, e.g. the Details button that opens the runtime inspector. */
  action?: ReactNode
  className?: string
}) {
  if (state === "idle") return null
  const copy = AI_RUNTIME_STATE_COPY[state]
  const live = state === "streaming" || state === "generating"
  return (
    <div
      role="status"
      aria-live="polite"
      data-gravitre-ai-runtime-state={state}
      data-fixture={fixture ? "true" : undefined}
      className={cn(
        "flex min-w-0 items-center gap-2 border-b border-divide bg-[color:var(--g-surface-1)] px-3 py-1.5 text-xs",
        className,
      )}
    >
      <span className={cn("flex items-center gap-1.5 font-medium", TONE[state])}>
        <span className="relative flex h-3.5 w-3.5 items-center justify-center">
          <StateIcon state={state} />
          {live ? (
            <span className="absolute inset-0 rounded-full bg-current opacity-20 motion-safe:animate-ping" aria-hidden />
          ) : null}
        </span>
        {copy.label}
      </span>
      <span className="min-w-0 truncate text-[color:var(--g-text-muted)]">{copy.detail}</span>
      {fixture ? (
        <span className="ml-auto shrink-0 rounded-sm border border-dashed border-[color:var(--g-warning)] px-1 py-px font-mono text-xs text-[color:var(--g-warning)] font-medium">
          Fixture
        </span>
      ) : null}
      {action ? <span className={cn("shrink-0", !fixture && "ml-auto")}>{action}</span> : null}
    </div>
  )
}
