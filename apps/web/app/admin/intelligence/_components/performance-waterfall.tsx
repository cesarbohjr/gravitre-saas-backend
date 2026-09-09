"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { readNumber } from "./shared"

export type WaterfallStage = {
  stage: string
  label: string
  avgMs: number
  p50Ms?: number
  p95Ms?: number
  count?: number
}

export function PerformanceWaterfall({
  title,
  subtitle,
  stages,
  emptyLabel,
  tone = "emerald",
}: {
  title: string
  subtitle: string
  stages: WaterfallStage[]
  emptyLabel: string
  tone?: "emerald" | "violet" | "cyan"
}) {
  const maxMs = Math.max(...stages.map((s) => readNumber(s.avgMs)), 1)
  const totalMs = stages.reduce((sum, s) => sum + readNumber(s.avgMs), 0)

  const toneBar = {
    emerald: "bg-emerald-500/80",
    violet: "bg-violet-500/75",
    cyan: "bg-cyan-500/75",
  }[tone]

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.12 }}
      className="rounded-xl border border-border/60 bg-background/40 p-4 ring-1 ring-border/40"
    >
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mb-3 text-xs text-muted-foreground">{subtitle}</p>
      {stages.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-[10px] tabular-nums text-muted-foreground">
            <span>0 ms</span>
            <span>{totalMs} ms cumulative (avg)</span>
          </div>
          <ul className="space-y-2" aria-label={title}>
            {stages.map((stage, index) => {
              const avg = readNumber(stage.avgMs)
              const widthPct = Math.max(4, Math.round((avg / maxMs) * 100))
              return (
                <li key={stage.stage} className="grid grid-cols-[minmax(7rem,9rem)_1fr_auto] items-center gap-2">
                  <span className="truncate text-xs text-muted-foreground">{stage.label}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-muted/60">
                    <motion.div
                      className={cn("h-full rounded-full", toneBar)}
                      initial={{ width: 0 }}
                      animate={{ width: `${widthPct}%` }}
                      transition={{ duration: 0.5, delay: index * 0.04, ease: [0.4, 0, 0.2, 1] }}
                    />
                  </div>
                  <span className="text-xs font-medium tabular-nums text-foreground">{avg} ms</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </motion.div>
  )
}
