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

/**
 * Memory category is a *taxonomy*, not a health signal, so it uses the
 * categorical `--chart-*` ramp rather than success/warning/error tones (which
 * would wrongly imply a rule is "bad"). Risk signal is the one genuine
 * severity case, so it keeps the destructive token.
 *
 * These tokens carry per-theme lightness, so the old `dark:` pairs are gone.
 */
const MEMORY_CATEGORY_CONFIG: Record<
  string,
  { icon: Icon; chipBg: string; iconColor: string; label: string }
> = {
  fact: {
    icon: BookOpen,
    chipBg: "bg-chart-2/10",
    iconColor: "text-chart-2",
    label: "Fact",
  },
  preference: {
    icon: UserCircle,
    chipBg: "bg-chart-4/10",
    iconColor: "text-chart-4",
    label: "Preference",
  },
  pattern: {
    icon: FlowArrow,
    chipBg: "bg-chart-1/10",
    iconColor: "text-chart-1",
    label: "Pattern",
  },
  rule: {
    icon: ShieldWarning,
    chipBg: "bg-chart-3/10",
    iconColor: "text-chart-3",
    label: "Rule",
  },
  business_rule: {
    icon: ShieldWarning,
    chipBg: "bg-chart-3/10",
    iconColor: "text-chart-3",
    label: "Business rule",
  },
  campaign_learning: {
    icon: Megaphone,
    chipBg: "bg-chart-5/10",
    iconColor: "text-chart-5",
    label: "Campaign learning",
  },
  risk_signal: {
    icon: ShieldWarning,
    chipBg: "bg-destructive/10",
    iconColor: "text-destructive",
    label: "Risk signal",
  },
  decision: {
    icon: Lightbulb,
    chipBg: "bg-chart-3/10",
    iconColor: "text-chart-3",
    label: "Decision",
  },
  outcome: {
    icon: FlowArrow,
    chipBg: "bg-chart-1/10",
    iconColor: "text-chart-1",
    label: "Outcome",
  },
  relationship: {
    icon: UserCircle,
    chipBg: "bg-chart-4/10",
    iconColor: "text-chart-4",
    label: "Relationship",
  },
  procedural: {
    icon: BookOpen,
    chipBg: "bg-chart-2/10",
    iconColor: "text-chart-2",
    label: "Procedural",
  },
  episodic: {
    icon: Megaphone,
    chipBg: "bg-chart-5/10",
    iconColor: "text-chart-5",
    label: "Episodic",
  },
  working: {
    icon: Lightbulb,
    chipBg: "bg-secondary/80",
    iconColor: "text-muted-foreground",
    label: "Working",
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
