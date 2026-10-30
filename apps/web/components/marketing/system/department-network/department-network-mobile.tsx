"use client"

/**
 * Mobile converge story — one relationship at a time (not a shrunk radial).
 * Core is the Nodus hub tile — no ring-spin.
 */

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { cn } from "@/lib/utils"
import type { CoreState, DepartmentId } from "./types"

type MobileBeat = {
  from: DepartmentId
  to: DepartmentId
  caption: string
}

const MOBILE_BEATS: MobileBeat[] = [
  {
    from: "sales",
    to: "support",
    caption: "Sales signal → Gravitre → Support returns context.",
  },
  {
    from: "sales",
    to: "finance",
    caption: "Gravitre coordinates Finance and Operations from the same intelligence.",
  },
  {
    from: "support",
    to: "operations",
    caption: "Outcomes return. A relationship stays — Learned.",
  },
]

const LABELS: Record<DepartmentId, string> = {
  sales: "Sales",
  support: "Support",
  operations: "Operations",
  finance: "Finance",
}

const APP_DEPARTMENT: Record<DepartmentId, string> = {
  sales: "sales",
  support: "customer_success",
  operations: "operations",
  finance: "finance",
}

function phaseToCoreState(phase: "from" | "core" | "to" | "back"): CoreState {
  switch (phase) {
    case "from":
      return "receiving"
    case "core":
      return "connecting"
    case "to":
      return "coordinating"
    case "back":
      return "learned"
  }
}

function MobileNode({
  id,
  active,
  resolved,
}: {
  id: DepartmentId
  active?: boolean
  resolved?: boolean
}) {
  return (
    <div
      className={cn(
        "w-full max-w-[15rem] overflow-hidden rounded-xl border bg-card shadow-[var(--shadow-aceternity)]",
        active && "border-brand",
        resolved && "border-[color:var(--info)]",
        !active && !resolved && "border-line",
      )}
    >
      <div className="flex items-center gap-1 border-b border-line px-3 py-1.5">
        <span className="size-1.5 rounded-full bg-line" />
        <span className="size-1.5 rounded-full bg-line" />
        <span className="size-1.5 rounded-full bg-line" />
        <span className="ml-1.5 font-mono text-[10px] text-[color:var(--g-text-muted)]">{LABELS[id].toLowerCase()}</span>
        <span className={cn("ml-auto size-1.5 rounded-full", active ? "bg-brand" : "bg-brand/60")} />
      </div>
      <div className="flex items-center gap-3 px-3 py-2.5">
        <DepartmentIcon department={APP_DEPARTMENT[id]} size="sm" />
        <span className="text-sm font-semibold text-[color:var(--g-text-primary)]">{LABELS[id]}</span>
      </div>
    </div>
  )
}

function MobileCore({ label, coreState }: { label: string; coreState: CoreState }) {
  const learned = coreState === "learned"

  return (
    <div className="flex flex-col items-center gap-2" data-testid="mobile-hub-core" data-core-state={coreState}>
      <div
        className={cn(
          "flex size-16 items-center justify-center rounded-2xl border bg-card shadow-[var(--shadow-aceternity)]",
          learned ? "border-brand" : "border-line",
        )}
      >
        <LogoSVG className="size-7 text-foreground" />
      </div>
      <span className="rounded-md border border-line bg-card px-2 py-0.5 text-[10px] font-semibold text-brand">
        {label}
      </span>
    </div>
  )
}

export function DepartmentNetworkMobile({ reduced }: { reduced: boolean }) {
  const [idx, setIdx] = useState(0)
  const [phase, setPhase] = useState<"from" | "core" | "to" | "back">("from")

  useEffect(() => {
    if (reduced) return
    const order: Array<"from" | "core" | "to" | "back"> = ["from", "core", "to", "back"]
    let step = 0
    const tick = () => {
      const next = order[step % order.length]
      if (next) setPhase(next)
      if (step > 0 && step % 4 === 0) {
        setIdx((i) => (i + 1) % MOBILE_BEATS.length)
      }
      step += 1
    }
    tick()
    const t = window.setInterval(tick, 1600)
    return () => window.clearInterval(t)
  }, [reduced])

  const beat = MOBILE_BEATS[idx] ?? MOBILE_BEATS[0]!
  const coreState = reduced ? "idle" : phaseToCoreState(phase)
  const coreLabel =
    phase === "from"
      ? "Receiving"
      : phase === "core"
        ? "Connecting context"
        : phase === "to"
          ? "Acting"
          : "Learned"

  return (
    <div className="mx-auto flex w-full max-w-sm flex-col items-center gap-3 px-2 py-4">
      <AnimatePresence mode="wait">
        <motion.div
          key={`${beat.from}-${beat.to}-${phase}`}
          initial={reduced ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduced ? undefined : { opacity: 0, y: -6 }}
          className="flex w-full flex-col items-center gap-3"
        >
          <MobileNode id={beat.from} active={phase === "from" || phase === "core"} resolved={phase === "back"} />
          <div
            className={cn(
              "h-8 w-px",
              phase === "from" || phase === "back"
                ? "bg-[color:var(--info)]"
                : "bg-brand",
            )}
            aria-hidden
          />
          <MobileCore label={reduced ? "Gravitre" : coreLabel} coreState={coreState} />
          <div
            className={cn(
              "h-8 w-px",
              phase === "to" || phase === "back"
                ? "bg-brand"
                : "bg-line",
            )}
            aria-hidden
          />
          <MobileNode id={beat.to} active={phase === "to"} resolved={phase === "back"} />
        </motion.div>
      </AnimatePresence>
      <p
        className="mt-2 max-w-xs text-center text-sm font-medium text-[color:var(--g-text-secondary)]"
        aria-live="polite"
      >
        {beat.caption}
      </p>
      <p className="max-w-xs text-center text-[11px] text-[color:var(--g-text-muted)]">
        Illustrative story — not live org telemetry.
      </p>
    </div>
  )
}
