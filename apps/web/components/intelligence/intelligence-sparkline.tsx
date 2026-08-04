"use client"

import { Line, LineChart, ResponsiveContainer } from "recharts"
import { cn } from "@/lib/utils"

export function IntelligenceSparkline({
  data,
  dataKey = "value",
  className,
  strokeClassName = "text-primary",
}: {
  data: Array<Record<string, number | string>>
  dataKey?: string
  className?: string
  strokeClassName?: string
}) {
  if (!data.length) {
    return <div className={cn("h-10 rounded-md bg-secondary/50", className)} aria-hidden />
  }

  return (
    <div className={cn("h-10 w-full", className)} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke="currentColor"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            // The line paints with `currentColor`, so the color must come from a
            // `text-*` class. The old default was `stroke-emerald-500`, which
            // could never take effect — the hardcoded `text-emerald-500` here
            // always won, silently ignoring any caller override.
            className={strokeClassName}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
