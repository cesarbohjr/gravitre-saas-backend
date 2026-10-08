"use client"

/**
 * Mobile converge story — one relationship at a time (not a shrunk radial).
 * Core uses Relational Topology (CES 1.0) — no ring-spin.
 */

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { PhoneIcon, RocketIcon, WalletIcon } from "@/components/marketing/nodus-icons/card-icons"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { topologyForCoreState } from "@/components/marketing/creative/primitives/relational-topology"
import { CREATIVE_TOKENS } from "@/components/marketing/creative/core/tokens"
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

const ICONS = {
  sales: RocketIcon,
  support: PhoneIcon,
  operations: NucleoWorkflow,
  finance: WalletIcon,
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
  const Icon = ICONS[id]
  return (
    <div
      className={cn(
        "flex w-full max-w-[14rem] items-center gap-3 rounded-xl border bg-card px-3 py-2.5 shadow-sm",
        active && "border-brand",
        resolved && "border-[color:var(--info)]",
        !active && !resolved && "border-line",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 text-[color:var(--g-text-secondary)]",
          active && "text-brand",
        )}
      />
      <span className="text-sm font-semibold text-[color:var(--g-text-secondary)]">{LABELS[id]}</span>
      <span
        className={cn(
          "ml-auto h-2 w-2 rounded-full",
          active ? "bg-brand" : "bg-line",
        )}
      />
    </div>
  )
}

function MobileCore({ label, coreState, reduced }: { label: string; coreState: CoreState; reduced: boolean }) {
  const layout = topologyForCoreState(coreState)
  const learned = coreState === "learned"

  return (
    <div className="flex flex-col items-center gap-2" data-testid="mobile-topology-core" data-core-state={coreState}>
      <div
        className={cn(
          "relative flex h-14 w-14 items-center justify-center overflow-hidden rounded-xl border bg-card shadow-sm",
          learned
            ? "border-brand"
            : "border-line",
        )}
      >
        <svg viewBox="0 0 80 72" className="absolute inset-0 h-full w-full" aria-hidden data-testid="mobile-topology-svg">
          {layout.edges.map(([a, b], i) => {
            const pa = layout.nodes[a]
            const pb = layout.nodes[b]
            if (!pa || !pb) return null
            const isInbound = layout.inboundIndex === a || layout.inboundIndex === b
            const isOutbound =
              layout.outboundIndices.includes(a) || layout.outboundIndices.includes(b)
            return (
              <line
                key={`me-${coreState}-${i}`}
                x1={pa.x}
                y1={pa.y}
                x2={pb.x}
                y2={pb.y}
                stroke={
                  isInbound
                    ? CREATIVE_TOKENS.signal
                    : isOutbound || learned
                      ? CREATIVE_TOKENS.action
                      : "color-mix(in srgb, var(--g-intelligence) 45%, var(--g-border-strong))"
                }
                strokeWidth={isOutbound || isInbound ? 1.5 : 1.1}
                strokeLinecap="round"
                opacity={reduced ? 0.85 : 1}
              />
            )
          })}
          {layout.nodes.map((p, i) => {
            const isCenter = i === 0
            return (
              <circle
                key={`mn-${coreState}-${i}`}
                cx={p.x}
                cy={p.y}
                r={isCenter ? 4.5 : 2.2}
                fill={
                  isCenter
                    ? CREATIVE_TOKENS.brand
                    : learned
                      ? CREATIVE_TOKENS.action
                      : "color-mix(in srgb, var(--g-intelligence) 55%, var(--muted-foreground))"
                }
              />
            )
          })}
        </svg>
        <div className="relative z-10 text-brand">
          <LogoSVG className="size-5 opacity-90" />
        </div>
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
          <MobileCore label={reduced ? "Gravitre" : coreLabel} coreState={coreState} reduced={reduced} />
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
