"use client"

/**
 * Hero proposition diagram — departments → shared brain → outcomes.
 * Motion explains the one-brain story (Design Pass 3).
 */

import { motion, AnimatePresence } from "framer-motion"
import { useEffect, useState } from "react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

const DEPARTMENTS = ["Sales", "Marketing", "Finance", "Operations", "Support", "HR", "IT"] as const
const OUTCOMES = ["Coordinated actions", "Measurable outcomes", "Continuous improvement"] as const

type Beat = "departments" | "brain" | "outcomes"

const BEAT_MS: Record<Beat, number> = {
  departments: 2800,
  brain: 2600,
  outcomes: 3000,
}

const SEQUENCE: Beat[] = ["departments", "brain", "outcomes"]

export function HeroBrainFlow({ className }: { className?: string }) {
  const { reduced } = useMotionPrefs()
  const [beat, setBeat] = useState<Beat>(reduced ? "brain" : "departments")

  useEffect(() => {
    if (reduced) return
    let i = 0
    let timer: ReturnType<typeof setTimeout>
    const tick = () => {
      const current = SEQUENCE[i] ?? "brain"
      setBeat(current)
      timer = setTimeout(() => {
        i = (i + 1) % SEQUENCE.length
        tick()
      }, BEAT_MS[current])
    }
    tick()
    return () => clearTimeout(timer)
  }, [reduced])

  return (
    <div
      className={cn(
        "relative mx-auto w-full max-w-4xl overflow-hidden rounded-2xl border border-border bg-card/80 p-5 shadow-[var(--g-shadow-product)] backdrop-blur-sm sm:p-8",
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,color-mix(in_oklch,var(--primary)_18%,transparent)_0%,transparent_65%)]" />

      <div className="relative grid gap-6 lg:grid-cols-[1fr_auto_1fr] lg:items-center lg:gap-4">
        {/* Departments */}
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Your business
          </p>
          <div className="flex flex-wrap gap-2 lg:flex-col lg:flex-nowrap">
            {DEPARTMENTS.map((dept, i) => (
              <motion.div
                key={dept}
                animate={
                  reduced
                    ? { opacity: 1, x: 0 }
                    : beat === "departments"
                      ? { opacity: 1, x: 0 }
                      : beat === "brain"
                        ? { opacity: 0.55, x: 6 }
                        : { opacity: 0.35, x: 0 }
                }
                transition={{ delay: reduced ? 0 : i * 0.05, duration: 0.45 }}
                className="rounded-lg border border-border bg-background/80 px-3 py-1.5 text-sm font-medium text-foreground"
              >
                {dept}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Shared brain */}
        <div className="relative flex flex-col items-center justify-center py-4">
          {!reduced ? (
            <motion.div
              aria-hidden
              className="absolute h-40 w-40 rounded-full bg-primary/25 blur-3xl"
              animate={{ scale: [1, 1.15, 1], opacity: [0.35, 0.55, 0.35] }}
              transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}
          <motion.div
            animate={
              reduced
                ? undefined
                : {
                    scale: beat === "brain" ? 1.06 : 1,
                    boxShadow:
                      beat === "brain"
                        ? "0 0 48px color-mix(in oklch, var(--primary) 45%, transparent)"
                        : "0 0 24px color-mix(in oklch, var(--primary) 25%, transparent)",
                  }
            }
            className="relative flex h-28 w-28 flex-col items-center justify-center rounded-full border-2 border-primary bg-background sm:h-32 sm:w-32"
          >
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
              Shared
            </span>
            <span className="mt-1 text-sm font-bold tracking-tight text-foreground">BRAIN</span>
            <span className="mt-0.5 text-[10px] text-muted-foreground">Gravitre</span>
          </motion.div>
          <AnimatePresence mode="wait">
            <motion.p
              key={beat}
              initial={reduced ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0 }}
              className="mt-4 text-center text-xs font-medium text-muted-foreground"
            >
              {beat === "departments"
                ? "Teams & functions connect in"
                : beat === "brain"
                  ? "One intelligence coordinates"
                  : "Outcomes the business can measure"}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* Outcomes */}
        <div className="space-y-2 lg:text-right">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Business outcomes
          </p>
          <div className="flex flex-wrap gap-2 lg:flex-col lg:flex-nowrap lg:items-end">
            {OUTCOMES.map((out, i) => (
              <motion.div
                key={out}
                animate={
                  reduced
                    ? { opacity: 1 }
                    : beat === "outcomes"
                      ? { opacity: 1, x: 0 }
                      : { opacity: 0.4, x: -4 }
                }
                transition={{ delay: reduced ? 0 : i * 0.08, duration: 0.45 }}
                className="rounded-lg border border-primary/35 bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary"
              >
                {out}
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
