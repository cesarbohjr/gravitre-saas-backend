"use client"

import {
  BookOpen,
  FlowArrow,
  Lightbulb,
  Megaphone,
  ShieldWarning,
  UserCircle,
} from "@phosphor-icons/react"
import type { Icon } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"

const MEMORY_CATEGORY_CONFIG: Record<
  string,
  { icon: Icon; chipBg: string; iconColor: string; label: string }
> = {
  fact: {
    icon: BookOpen,
    chipBg: "bg-sky-500/10",
    iconColor: "text-sky-600 dark:text-sky-400",
    label: "Fact",
  },
  preference: {
    icon: UserCircle,
    chipBg: "bg-violet-500/10",
    iconColor: "text-violet-600 dark:text-violet-400",
    label: "Preference",
  },
  pattern: {
    icon: FlowArrow,
    chipBg: "bg-indigo-500/10",
    iconColor: "text-indigo-600 dark:text-indigo-400",
    label: "Pattern",
  },
  rule: {
    icon: ShieldWarning,
    chipBg: "bg-amber-500/10",
    iconColor: "text-amber-700 dark:text-amber-300",
    label: "Rule",
  },
  business_rule: {
    icon: ShieldWarning,
    chipBg: "bg-amber-500/10",
    iconColor: "text-amber-700 dark:text-amber-300",
    label: "Business rule",
  },
  campaign_learning: {
    icon: Megaphone,
    chipBg: "bg-rose-500/10",
    iconColor: "text-rose-600 dark:text-rose-400",
    label: "Campaign learning",
  },
  risk_signal: {
    icon: ShieldWarning,
    chipBg: "bg-red-500/10",
    iconColor: "text-red-600 dark:text-red-400",
    label: "Risk signal",
  },
}

const DEFAULT_CONFIG = {
  icon: Lightbulb,
  chipBg: "bg-secondary/80",
  iconColor: "text-muted-foreground",
  label: "Memory",
}

export function MemoryCategoryChip({
  category,
  size = "sm",
  showLabel = true,
  className,
}: {
  category?: string | null
  size?: "sm" | "md"
  showLabel?: boolean
  className?: string
}) {
  const key = String(category || "memory").toLowerCase().replace(/\s+/g, "_")
  const config = MEMORY_CATEGORY_CONFIG[key] ?? DEFAULT_CONFIG
  const Icon = config.icon
  const px = size === "md" ? 32 : 24
  const iconPx = size === "md" ? 16 : 12

  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className={cn("inline-flex shrink-0 items-center justify-center rounded-lg", config.chipBg)}
        style={{ width: px, height: px }}
        aria-hidden
      >
        <Icon size={iconPx} weight="duotone" className={config.iconColor} />
      </span>
      {showLabel ? (
        <span className="text-xs font-medium capitalize text-foreground">{config.label}</span>
      ) : null}
    </span>
  )
}

export function memoryCategoryBreakdown(
  memories: Array<{ category?: string | null; memory_category?: string | null }>,
): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const row of memories) {
    const key = String(row.category ?? row.memory_category ?? "other").toLowerCase()
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}
