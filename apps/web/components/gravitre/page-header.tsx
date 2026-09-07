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
        "min-w-0 px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:py-3.5",
        !className?.includes("border") && "border-b border-divide",
        className,
      )}
    >
      <div className="mb-3 flex min-w-0 flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className={cn(
                "flex shrink-0 items-center justify-center rounded-[var(--np-radius-md)] ring-1",
                usesBrandTint
                  ? "bg-[color:var(--g-brand-soft)] ring-[color:var(--g-brand-border)]"
                  : cn("bg-gradient-to-br ring-border/60", tint),
              )}
              style={{ width: 36, height: 36, minWidth: 36, minHeight: 36 }}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  usesBrandTint ? "text-[color:var(--g-brand)]" : "text-foreground",
                )}
              />
            </motion.div>
          )}
          <div className="min-w-0 space-y-0.5">
            {eyebrow || eyebrowAccessory ? (
              <div className="flex flex-wrap items-center gap-2">
                {eyebrow ? <p className={TYPE.eyebrow}>{eyebrow}</p> : null}
                {eyebrowAccessory}
              </div>
            ) : null}
            <h1 className={TYPE.pageTitle}>{title}</h1>
            {description && <p className={TYPE.pageLead}>{description}</p>}
          </div>
        </div>
        {actions && (
          <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            {actions}
          </div>
        )}
      </div>
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
  const variantStyles = {
    default: "border-divide bg-[color:var(--g-surface-1)]",
    success: "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]",
    warning: "border-amber-300/50 bg-amber-500/10",
    info: "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)]",
    danger: "border-destructive/25 bg-destructive/10",
  }

  const valueColors = {
    default: "text-[color:var(--g-text-primary)]",
    success: "text-[color:var(--g-brand)]",
    warning: "text-amber-800",
    info: "text-[color:var(--g-brand-active)]",
    danger: "text-destructive",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "border p-2.5 text-center shadow-[var(--np-shadow)] sm:p-3",
        "rounded-[var(--np-radius-lg)]",
        variantStyles[variant],
        className
      )}
    >
      <div className={cn("text-base font-semibold tabular-nums sm:text-lg", valueColors[variant])}>
        {value}
      </div>
      <div className={cn(TYPE.metricLabel, "mt-0.5 text-[color:var(--g-text-muted)]")}>{label}</div>
    </motion.div>
  )
}
