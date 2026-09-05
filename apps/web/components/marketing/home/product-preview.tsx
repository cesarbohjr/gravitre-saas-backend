"use client"

import { motion, useScroll, useTransform } from "framer-motion"
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
  intent: 1100,
  agent: 1400,
  context: 1300,
  tool: 1400,
  approval: 1600,
  verified: 1500,
  calm: 2200,
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

/** Dominant hero visual — truthful status rhythm (no fabricated %). */
export function ProductPreview() {
  const ref = useRef(null)
  const { reduced } = useMotionPrefs()
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  })
  const y = useTransform(scrollYProgress, [0, 1], [reduced ? 0 : 100, reduced ? 0 : -100])
  const opacity = useTransform(
    scrollYProgress,
    [0, 0.3, 0.7, 1],
    reduced ? [1, 1, 1, 1] : [0, 1, 1, 0],
  )

  const [beat, setBeat] = useState<DemoBeat>(reduced ? "calm" : "intent")

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

  const intelligenceActive =
    beat === "agent" || beat === "context" || beat === "tool"
  const operationalActive = beat === "verified"

  return (
    <motion.div ref={ref} style={{ y, opacity }} className="relative">
      <div
        className={cn(
          "absolute -inset-4 rounded-3xl blur-2xl transition-opacity duration-700",
          operationalActive
            ? "bg-[color:var(--g-emerald)]/25 opacity-100"
            : intelligenceActive
              ? "bg-[color:var(--g-intelligence)]/20 opacity-90"
              : "bg-primary/15 opacity-70",
        )}
      />
      {/* Agenforce-style product shell: light UI on dark field, soft bottom fade */}
      <div
        className="relative rounded-2xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-2 shadow-[var(--g-shadow-elevated)]"
        style={{
          boxShadow: operationalActive
            ? "var(--g-glow-operational)"
            : "var(--highlight-edge), var(--g-shadow-elevated)",
          maskImage:
            "linear-gradient(to bottom, black 0%, black 72%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, black 0%, black 72%, transparent 100%)",
        }}
      >
        <div className="overflow-hidden rounded-xl border border-[color:var(--g-border-subtle)] bg-muted/40">
          <div className="flex items-center gap-2 border-b border-border bg-[color:var(--g-surface-1)] px-4 py-3">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-muted-foreground/35" />
              <div className="h-3 w-3 rounded-full bg-muted-foreground/25" />
              <div className="h-3 w-3 rounded-full bg-primary/55" />
            </div>
            <div className="flex-1 text-center">
              <span className="font-mono text-xs text-muted-foreground">gravitre.app/ai</span>
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
          <div className="aspect-[16/9] bg-gradient-to-br from-muted/50 to-[color:var(--g-surface-1)] p-6 sm:p-8">
            <div className="grid h-full grid-cols-12 gap-4">
              <div
                className="col-span-3 rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 shadow-[var(--g-shadow-surface)]"
                style={{ boxShadow: "var(--highlight-edge), var(--g-shadow-surface)" }}
              >
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div
                        className={cn(
                          "h-2 w-2 rounded-full transition-colors duration-500",
                          i === 2 && intelligenceActive
                            ? "bg-[color:var(--g-intelligence)]"
                            : i === 2
                              ? "bg-primary"
                              : "bg-muted-foreground/30",
                        )}
                      />
                      <div
                        className={cn(
                          "h-2 rounded transition-all duration-500",
                          i === 2
                            ? "w-16 bg-muted-foreground/50"
                            : "w-12 bg-muted-foreground/25",
                        )}
                      />
                    </div>
                  ))}
                </div>
              </div>
              <div className="col-span-6 space-y-4">
                <div
                  className={cn(
                    "rounded-lg border p-4 shadow-[var(--g-shadow-surface)] transition-colors duration-500",
                    intelligenceActive
                      ? "border-[color:var(--g-intelligence)]/30 bg-[color:var(--g-surface-active)]"
                      : "border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]",
                  )}
                  style={{
                    boxShadow: intelligenceActive
                      ? "var(--g-highlight-intelligence), var(--g-shadow-surface)"
                      : "var(--highlight-edge), var(--g-shadow-surface)",
                  }}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-full shadow-md transition-colors duration-500",
                        intelligenceActive
                          ? "bg-[color:var(--g-intelligence)] text-white"
                          : operationalActive
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground",
                      )}
                    >
                      <span className="text-xs font-semibold tracking-wide">
                        {beat === "approval" ? "GOV" : beat === "verified" ? "OK" : "AI"}
                      </span>
                    </div>
                    <div className="flex-1 space-y-1.5">
                      <div className="h-2 w-32 rounded bg-muted-foreground/40" />
                      <div className="h-2 w-24 rounded bg-muted-foreground/25" />
                    </div>
                  </div>
                </div>
                <div
                  className={cn(
                    "rounded-lg border p-4 transition-colors duration-500",
                    beat === "approval"
                      ? "border-[color:var(--g-warning)]/35 bg-[color:var(--g-warning)]/10"
                      : operationalActive
                        ? "border-primary/30 bg-primary/10"
                        : "border-[color:var(--g-intelligence)]/20 bg-[color:var(--g-intelligence)]/8",
                  )}
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      {beat === "tool"
                        ? "Tool invoke"
                        : beat === "approval"
                          ? "Human gate"
                          : beat === "verified"
                            ? "Outcome"
                            : "Turn"}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{statusLabel}</span>
                  </div>
                  <motion.div
                    className={cn(
                      "h-2 rounded",
                      beat === "approval"
                        ? "bg-[color:var(--g-warning)]/60"
                        : operationalActive
                          ? "bg-primary/60"
                          : "bg-[color:var(--g-intelligence)]/50",
                    )}
                    animate={
                      reduced || beat === "calm"
                        ? { width: "100%" }
                        : { width: ["12%", "100%"] }
                    }
                    transition={
                      reduced
                        ? { duration: 0 }
                        : { duration: (BEAT_MS[beat] ?? 1200) / 1000, ease: "easeInOut" }
                    }
                    key={beat}
                  />
                </div>
              </div>
              <div
                className="col-span-3 rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 shadow-[var(--g-shadow-surface)]"
                style={{ boxShadow: "var(--highlight-edge), var(--g-shadow-surface)" }}
              >
                <div className="mb-3 text-xs font-medium text-muted-foreground">Metrics</div>
                <div className="space-y-3">
                  <div>
                    <div className="mb-1 text-xs leading-snug text-muted-foreground">
                      {success.eyebrow}
                    </div>
                    <div
                      className={cn(
                        "text-sm font-medium leading-snug transition-colors duration-500",
                        operationalActive ? "text-primary" : "text-foreground",
                      )}
                    >
                      {success.primary}
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
                      Live run telemetry in your workspace — never a fabricated public %
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
