"use client"

/**
 * Mobile converge story — one relationship at a time (not a shrunk radial).
 */

import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import { PhoneIcon, RocketIcon, WalletIcon } from "@/components/marketing/nodus-icons/card-icons"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { cn } from "@/lib/utils"
import type { DepartmentId } from "./types"

type MobileBeat = {
  from: DepartmentId
  to: DepartmentId
  caption: string
}

const MOBILE_BEATS: MobileBeat[] = [
  { from: "sales", to: "support", caption: "Sales creates a signal. Support receives what it needs." },
  { from: "support", to: "finance", caption: "Support creates a signal. Finance works from the same intelligence." },
  { from: "sales", to: "operations", caption: "One business event. Multiple coordinated departments." },
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
        "flex w-full max-w-[14rem] items-center gap-3 rounded-xl border bg-white px-3 py-2.5 shadow-sm",
        active && "border-[color:var(--color-brand,#16a374)]",
        resolved && "border-[color:var(--color-blue-500)]",
        !active && !resolved && "border-[color:var(--color-line,#eaedf1)]",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 text-[color:var(--g-text-secondary)]",
          active && "text-[color:var(--color-brand,#16a374)]",
        )}
      />
      <span className="text-sm font-semibold text-[color:var(--g-text-secondary)]">{LABELS[id]}</span>
      <span
        className={cn(
          "ml-auto h-2 w-2 rounded-full",
          active ? "bg-[color:var(--color-brand,#16a374)]" : "bg-[color:var(--color-line,#eaedf1)]",
        )}
      />
    </div>
  )
}

function MobileCore({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative flex h-14 w-14 items-center justify-center overflow-hidden rounded-xl border border-[color:var(--color-line,#eaedf1)] bg-white shadow-sm">
        <div className="absolute inset-0 animate-spin rounded-full opacity-70 [animation-duration:3s] [background-image:conic-gradient(at_center,transparent,color-mix(in_oklch,var(--color-brand,#16a374)_35%,transparent)_18%,transparent_32%)]" />
        <div className="relative z-10 text-[color:var(--color-brand,#16a374)]">
          <LogoSVG className="size-6" />
        </div>
      </div>
      <span className="rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2 py-0.5 text-[10px] font-semibold text-[color:var(--color-brand,#16a374)]">
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
                ? "bg-[color:var(--color-blue-500)]"
                : "bg-[color:var(--color-brand,#16a374)]",
            )}
            aria-hidden
          />
          <MobileCore label={reduced ? "Gravitre" : coreLabel} />
          <div
            className={cn(
              "h-8 w-px",
              phase === "to" || phase === "back"
                ? "bg-[color:var(--color-brand,#16a374)]"
                : "bg-[color:var(--color-line,#eaedf1)]",
            )}
            aria-hidden
          />
          <MobileNode id={beat.to} active={phase === "to"} resolved={phase === "back"} />
        </motion.div>
      </AnimatePresence>
      <p className="mt-2 max-w-xs text-center text-sm font-medium text-[color:var(--g-text-secondary)]">
        {beat.caption}
      </p>
    </div>
  )
}
