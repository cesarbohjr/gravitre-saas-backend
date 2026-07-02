"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { progressBarClass } from "@/components/gravitre/chart-brand"

type AnimatedMetricBarProps = {
  label: string
  value: number
  displayValue: string
  index?: number
  barClassName?: string
  className?: string
}

export function AnimatedMetricBar({
  label,
  value,
  displayValue,
  index = 0,
  barClassName,
  className,
}: AnimatedMetricBarProps) {
  const pct = Math.max(0, Math.min(100, value))
  const fillClass = barClassName ?? progressBarClass(pct)

  return (
    <li className={cn("-mx-1.5 flex items-center gap-3 rounded-md px-1.5 py-1.5 transition-colors hover:bg-muted/50", className)}>
      <span className="min-w-0 flex-1 truncate text-xs text-foreground">{label}</span>
      <span className="relative h-2 w-28 shrink-0 overflow-hidden rounded-full bg-secondary/60 sm:w-36">
        <motion.span
          className={cn("absolute inset-y-0 left-0 rounded-full", fillClass)}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.75, delay: 0.08 + index * 0.05, ease: "easeOut" }}
        />
      </span>
      <span className="w-12 shrink-0 text-right text-xs font-medium tabular-nums text-foreground">{displayValue}</span>
    </li>
  )
}
