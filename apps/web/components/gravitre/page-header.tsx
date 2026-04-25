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
  iconColor = "from-blue-500/20 to-cyan-500/20",
  actions,
  children,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("p-4 sm:p-6 border-b border-border", className)}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-white/10",
                iconColor
              )}
            >
              <Icon className="h-5 w-5 text-foreground" />
            </motion.div>
          )}
          <div>
            <h1 className="text-lg font-semibold text-foreground">{title}</h1>
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
        columns === 3 && "grid-cols-3",
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
  value: string | number
  variant?: "default" | "success" | "warning" | "info" | "danger"
  className?: string
}

export function StatCard({
  label,
  value,
  variant = "default",
  className,
}: StatCardProps) {
  const variantStyles = {
    default: "bg-secondary/50",
    success: "bg-emerald-500/10 border-emerald-500/20",
    warning: "bg-amber-500/10 border-amber-500/20",
    info: "bg-blue-500/10 border-blue-500/20",
    danger: "bg-red-500/10 border-red-500/20",
  }

  const valueColors = {
    default: "text-foreground",
    success: "text-emerald-400",
    warning: "text-amber-400",
    info: "text-blue-400",
    danger: "text-red-400",
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
