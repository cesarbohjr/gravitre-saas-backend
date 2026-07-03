"use client"

import { AlertTriangle, TrendingUp } from "lucide-react"
import { cn } from "@/lib/utils"

export type BusinessSignal = {
  id?: string
  title?: string
  summary?: string
  confidence?: number
  quality_score?: number
  signal_type?: string
  source?: string
}

export function BusinessSignalsBanner({ signals }: { signals: BusinessSignal[] | null | undefined }) {
  if (!signals?.length) return null

  const top = signals.slice(0, 3)

  return (
    <div className="border-b border-border bg-amber-50/60 px-4 py-2 md:px-6 dark:bg-amber-950/20">
      <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
        Proactive business signals
      </p>
      <ul className="space-y-1">
        {top.map((signal) => {
          const isRisk = signal.signal_type === "risk" || signal.signal_type === "alert"
          const Icon = isRisk ? AlertTriangle : TrendingUp
          const score = signal.quality_score ?? signal.confidence
          return (
            <li
              key={signal.id ?? signal.title}
              className="flex items-start gap-2 text-xs text-foreground/90"
            >
              <Icon
                className={cn(
                  "mt-0.5 h-3.5 w-3.5 shrink-0",
                  isRisk ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400",
                )}
              />
              <span>
                <span className="font-medium">{signal.title}</span>
                {signal.summary ? <span className="text-muted-foreground"> — {signal.summary}</span> : null}
                {score != null ? (
                  <span className="ml-1 text-[10px] text-muted-foreground">
                    ({Math.round(score * 100)}% relevance)
                  </span>
                ) : null}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
