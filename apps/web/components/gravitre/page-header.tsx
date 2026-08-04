"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { type LucideIcon } from "lucide-react"

interface PageHeaderProps {
  title: string
  description?: string
  icon?: LucideIcon
  iconColor?: string
  actions?: React.ReactNode
  children?: React.ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  // Default to the brand gradient (was off-brand blue/cyan). Consumers can
  // still override via iconColor; cn()/twMerge keeps the last color utility.
  iconColor = "from-primary/20 to-primary/5",
  actions,
  children,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("p-4 sm:p-6", !className?.includes("border") && "border-b border-border", className)}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className={cn(
                // ring-border is theme-aware (was ring-white/10, invisible in
                // light mode). Consumers appending ring-* still override it.
                "flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-border",
                iconColor
              )}
            >
              <Icon className="h-5 w-5 text-foreground" />
            </motion.div>
          )}
          <div>
            <h1 className="text-xl font-semibold text-foreground">{title}</h1>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
        {actions && (
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
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
        "grid gap-2 sm:gap-3",
        columns === 2 && "grid-cols-2",
        // Start at 2 cols on small phones so labels like "Recommendation
        // success rate" aren't crushed, then expand to 3 from sm up.
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
    default: "bg-secondary/50",
    success: "border-success/20 bg-success/10",
    warning: "border-warning/20 bg-warning/10",
    info: "border-info/20 bg-info/10",
    danger: "border-destructive/20 bg-destructive/10",
  }

  const valueColors = {
    default: "text-foreground",
    success: "text-success",
    warning: "text-warning",
    info: "text-info",
    danger: "text-destructive",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-lg p-2 sm:p-3 text-center border border-transparent",
        variantStyles[variant],
        className
      )}
    >
      <div className={cn("text-lg sm:text-xl font-semibold", valueColors[variant])}>
        {value}
      </div>
      <div className="text-[9px] sm:text-[10px] text-muted-foreground uppercase tracking-wider">
        {label}
      </div>
    </motion.div>
  )
}
