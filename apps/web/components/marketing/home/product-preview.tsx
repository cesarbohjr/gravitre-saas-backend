"use client"

/**
 * Dominant hero visual — real Gravitre product captures + truthful STATUS rhythm.
 * Perspective + fade-into-system (Agenforce craft, Gravitre product truth).
 */

import Image from "next/image"
import { motion, useScroll, useTransform, AnimatePresence } from "framer-motion"
import { useEffect, useRef, useState } from "react"
import { buildOperationalSuccessClaim, EMPTY_LIVE_INTEL } from "@/lib/marketing-intelligence-truth"
import { useMotionPrefs } from "@/lib/animations"
import { STATUS } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type DemoBeat =
  | "intent"
  | "agent"
  | "context"
  | "tool"
  | "approval"
  | "verified"
  | "calm"

const BEAT_MS: Record<DemoBeat, number> = {
  intent: 1200,
  agent: 1500,
  context: 1400,
  tool: 1500,
  approval: 1700,
  verified: 1600,
  calm: 2400,
}

const SEQUENCE: DemoBeat[] = [
  "intent",
  "agent",
  "context",
  "tool",
  "approval",
  "verified",
  "calm",
]

/** Map beats to real product captures (fixture screenshots, not live metrics). */
const BEAT_SHOT: Record<DemoBeat, { src: string; chrome: string }> = {
  intent: { src: "/product/app-ai.png", chrome: "gravitre.app/ai" },
  agent: { src: "/product/app-agents.png", chrome: "gravitre.app/agents" },
  context: { src: "/product/app-ai.png", chrome: "gravitre.app/ai" },
  tool: { src: "/product/app-connectors.png", chrome: "gravitre.app/connectors" },
  approval: { src: "/product/app-approvals.png", chrome: "gravitre.app/approvals" },
  verified: { src: "/product/app-activity.png", chrome: "gravitre.app/activity" },
  calm: { src: "/product/app-workflows.png", chrome: "gravitre.app/workflows" },
}

export function ProductPreview() {
  const ref = useRef(null)
  const { reduced } = useMotionPrefs()
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  })
  const y = useTransform(scrollYProgress, [0, 1], [reduced ? 0 : 80, reduced ? 0 : -60])
  const opacity = useTransform(
    scrollYProgress,
    [0, 0.2, 0.75, 1],
    reduced ? [1, 1, 1, 1] : [0.2, 1, 1, 0.35],
  )
  const rotateX = useTransform(scrollYProgress, [0, 0.5], [reduced ? 0 : 8, reduced ? 0 : 2])

  const [beat, setBeat] = useState<DemoBeat>(reduced ? "calm" : "intent")
  const [mobile, setMobile] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)")
    const apply = () => setMobile(mq.matches)
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [])

  useEffect(() => {
    if (reduced) return
    let i = 0
    let timer: ReturnType<typeof setTimeout>
    const tick = () => {
      const current = SEQUENCE[i] ?? "calm"
      setBeat(current)
      timer = setTimeout(() => {
        i = (i + 1) % SEQUENCE.length
        tick()
      }, BEAT_MS[current])
    }
    tick()
    return () => clearTimeout(timer)
  }, [reduced])

  const success = buildOperationalSuccessClaim(EMPTY_LIVE_INTEL)
  const shot = BEAT_SHOT[beat]
  const statusLabel =
    beat === "intent"
      ? "Intent received"
      : beat === "agent"
        ? "Agent active"
        : beat === "context"
          ? "Context retrieval"
          : beat === "tool"
            ? "Tool selected"
            : beat === "approval"
              ? "Needs approval"
              : beat === "verified"
                ? "Verified outcome"
                : "Ready"

  const statusClass =
    beat === "approval"
      ? STATUS.pending
      : beat === "verified"
        ? STATUS.verified
        : beat === "calm" || beat === "intent"
          ? STATUS.idle
          : STATUS.running

  const intelligenceActive = beat === "agent" || beat === "context" || beat === "tool"
  const operationalActive = beat === "verified"

  return (
    <motion.div
      ref={ref}
      style={{ y, opacity, rotateX: mobile || reduced ? 0 : rotateX }}
      className="relative mx-auto max-w-5xl"
    >
      <div
        className={cn(
          "absolute -inset-8 rounded-[2rem] blur-3xl transition-opacity duration-700",
          operationalActive
            ? "bg-[color:var(--g-emerald)]/12 opacity-90"
            : intelligenceActive
              ? "bg-[color:var(--g-intelligence)]/10 opacity-85"
              : beat === "approval"
                ? "bg-[color:var(--g-warning)]/8 opacity-70"
                : "bg-[color:var(--g-intelligence)]/7 opacity-60",
        )}
      />

      <div
        className={cn(
          "relative",
          !mobile &&
            !reduced &&
            "[transform:perspective(1600px)_rotateX(6deg)_rotateY(-3deg)] origin-top",
        )}
      >
        <div
          className="relative overflow-hidden rounded-2xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-1.5 shadow-[var(--g-shadow-product)] sm:p-2"
          style={{
            boxShadow: operationalActive
              ? "var(--g-highlight-top), var(--g-glow-operational), var(--g-shadow-product)"
              : intelligenceActive
                ? "var(--g-highlight-top), var(--g-glow-intelligence), var(--g-shadow-product)"
                : "var(--g-highlight-top), var(--g-shadow-product)",
            maskImage:
              "linear-gradient(to bottom, black 0%, black 70%, transparent 100%)",
            WebkitMaskImage:
              "linear-gradient(to bottom, black 0%, black 70%, transparent 100%)",
          }}
        >
          <div className="overflow-hidden rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)]">
            <div className="flex items-center gap-2 border-b border-border bg-[color:var(--g-surface-1)] px-4 py-3">
              <div className="flex gap-1.5">
                <div className="h-2.5 w-2.5 rounded-full bg-muted-foreground/35" />
                <div className="h-2.5 w-2.5 rounded-full bg-muted-foreground/25" />
                <div className="h-2.5 w-2.5 rounded-full bg-[color:var(--g-emerald)]/55" />
              </div>
              <div className="flex-1 text-center">
                <span className="font-mono text-[10px] text-muted-foreground sm:text-xs">
                  {shot.chrome}
                </span>
              </div>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide",
                  statusClass,
                )}
              >
                {statusLabel}
              </span>
            </div>

            <div className="relative aspect-[16/10] bg-[color:var(--g-void)] sm:aspect-[16/9]">
              <AnimatePresence mode="wait">
                <motion.div
                  key={shot.src + beat}
                  initial={reduced ? false : { opacity: 0.35, scale: 1.01 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={reduced ? undefined : { opacity: 0.2 }}
                  transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
                  className="absolute inset-0"
                >
                  <Image
                    src={shot.src}
                    alt={`Gravitre product surface — ${statusLabel}`}
                    fill
                    priority
                    sizes="(min-width: 1024px) 960px, 100vw"
                    className="object-cover object-top"
                  />
                </motion.div>
              </AnimatePresence>

              {/* State ribbon — truthful beat, not fake metrics */}
              <div className="absolute inset-x-3 bottom-3 z-10 sm:inset-x-5 sm:bottom-5">
                <div
                  className={cn(
                    "flex flex-wrap items-center justify-between gap-2 rounded-xl border px-3 py-2.5 backdrop-blur-md sm:px-4",
                    beat === "approval"
                      ? "border-[color:var(--g-warning)]/30 bg-[color:var(--g-surface-1)]/90"
                      : operationalActive
                        ? "border-[color:var(--g-emerald)]/30 bg-[color:var(--g-surface-1)]/90"
                        : "border-[color:var(--g-intelligence)]/25 bg-[color:var(--g-surface-1)]/90",
                  )}
                >
                  <div className="min-w-0">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      {beat === "tool"
                        ? "Tool invoke"
                        : beat === "approval"
                          ? "Human gate"
                          : beat === "verified"
                            ? "Outcome"
                            : intelligenceActive
                              ? "Intelligence"
                              : "System"}
                    </p>
                    <p className="truncate text-sm font-medium text-foreground">{statusLabel}</p>
                  </div>
                  <div className="max-w-[14rem] text-right">
                    <p className="text-[10px] text-muted-foreground">{success.eyebrow}</p>
                    <p
                      className={cn(
                        "text-xs font-medium",
                        operationalActive ? "text-[color:var(--g-emerald)]" : "text-foreground",
                      )}
                    >
                      {success.primary}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
