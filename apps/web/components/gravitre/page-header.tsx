"use client"

import type { ComponentType } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

/** Lucide or Nucleo semantic icons — only `className` is required at call sites. */
type HeaderIcon = ComponentType<{ className?: string }>

interface PageHeaderProps {
  title: string
  description?: string
  icon?: HeaderIcon
  iconColor?: string
  actions?: React.ReactNode
  children?: React.ReactNode
  className?: string
  /**
   * Small caps label above the title, e.g. "Gravitre Marketplace".
   * Renders with the single canonical eyebrow tracking value.
   */
  eyebrow?: string
  /** Inline node beside the eyebrow, typically a count pill. */
  eyebrowAccessory?: React.ReactNode
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  iconColor,
  actions,
  children,
  className,
  eyebrow,
  eyebrowAccessory,
}: PageHeaderProps) {
  // Default to the brand gradient (was off-brand blue/cyan). Consumers can
  // still override via iconColor; cn()/twMerge keeps the last color utility.
  const usesBrandTint = iconColor === undefined
  const tint = iconColor ?? "from-primary/15 to-primary/5"

  return (
    <div
      className={cn(
        "min-w-0 px-[var(--np-page-pad-sm)] pt-4 pb-3 sm:px-[var(--np-page-pad)] sm:pt-5",
        !className?.includes("border") && "border-b border-[color:var(--g-border-subtle)]",
        className,
      )}
    >
      {/* Title + actions share a row; description is full-width below so long
          leads cannot squeeze into a ~1-word column and inflate header height. */}
      <div className="mb-2 flex min-w-0 flex-col justify-between gap-3 sm:mb-2.5 sm:flex-row sm:items-center">
        <div className="flex min-w-0 shrink-0 items-center gap-2.5 sm:max-w-[min(100%,28rem)]">
          {Icon && (
            <span
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-background text-foreground",
                !usesBrandTint && cn("bg-gradient-to-br", tint),
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
            </span>
          )}
          <div className="min-w-0 space-y-0.5">
            {eyebrow || eyebrowAccessory ? (
              <div className="flex flex-wrap items-center gap-2">
                {eyebrow ? <p className={TYPE.eyebrow}>{eyebrow}</p> : null}
                {eyebrowAccessory}
              </div>
            ) : null}
            <h1 className={TYPE.pageTitle}>{title}</h1>
          </div>
        </div>
        {actions && (
          <div className="flex w-full min-w-0 flex-wrap items-center gap-2 sm:w-auto sm:flex-1 sm:justify-end">
            {actions}
          </div>
        )}
      </div>
      {description ? (
        <p className={cn(TYPE.pageLead, "-mt-1 mb-3 max-w-2xl text-pretty")}>{description}</p>
      ) : null}
      {children}
    </div>
  )
}

interface StatsGridProps {
  children: React.ReactNode
  columns?: 2 | 3 | 4
  className?: string
}

export function StatsGrid({ children, columns = 3, className }: StatsGridProps) {
  return (
    <div
      className={cn(
        "grid gap-[var(--np-kpi-gap)]",
        columns === 2 && "grid-cols-2",
        columns === 3 && "grid-cols-2 sm:grid-cols-3",
        columns === 4 && "grid-cols-2 sm:grid-cols-4",
        className
      )}
    >
      {children}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: React.ReactNode
  variant?: "default" | "success" | "warning" | "info" | "danger"
  className?: string
}

export function StatCard({
  label,
  value,
  variant = "default",
  className,
}: StatCardProps) {
  // Semantic tokens rather than raw palette hues: the fixed `-400` value colors
  // were tuned for dark mode and failed contrast against a 10% tint in light
  // mode. The `--success`/`--warning`/`--info`/`--destructive` tokens already
  // carry per-theme values.
  // Status is carried by a small marker, not a tinted tile: a row of colored
  // boxes competes with the page's real attention items.
  const markerColors = {
    default: "bg-[color:var(--g-border-strong)]",
    success: "bg-[color:var(--g-success)]",
    warning: "bg-[color:var(--g-warning)]",
    info: "bg-[color:var(--g-signal)]",
    danger: "bg-destructive",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2.5",
        className
      )}
    >
      <div className={cn(TYPE.metricLabel, "flex items-center gap-1.5")}>
        <span aria-hidden className={cn("size-1.5 rounded-full", markerColors[variant])} />
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-[color:var(--g-text-primary)] sm:text-xl">
        {value}
      </div>
    </motion.div>
  )
}
