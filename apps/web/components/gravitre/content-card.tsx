"use client"

import { forwardRef, type ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { type LucideIcon } from "lucide-react"
import { Icon, type IconName } from "@/lib/icons"

// =============================================================================
// ContentCard - Primary card component for displaying content blocks
// =============================================================================

interface ContentCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Visual variant */
  variant?: "default" | "elevated" | "ghost" | "interactive" | "highlight"
  /** Size variant affecting padding */
  size?: "sm" | "md" | "lg"
  /** Enable hover effects */
  hoverable?: boolean
  /** Enable ambient glow effect */
  glow?: boolean
  /** Glow color (requires glow=true) */
  glowColor?: "blue" | "emerald" | "violet" | "amber" | "rose"
  /** Show loading skeleton state */
  loading?: boolean
  /** Disable the card */
  disabled?: boolean
  children: ReactNode
}

const sizeStyles = {
  sm: "p-3",
  md: "p-4",
  lg: "p-5 sm:p-6",
}

const variantStyles = {
  default: "border border-border bg-card",
  elevated: "border border-border bg-card shadow-lg shadow-black/5",
  ghost: "border-transparent bg-transparent hover:bg-secondary/50",
  interactive: "border border-border bg-card cursor-pointer hover:border-muted-foreground/40 hover:bg-accent/50",
  highlight: "border border-primary/20 bg-primary/5",
}

const glowColors = {
  blue: "shadow-blue-500/10 hover:shadow-blue-500/20",
  emerald: "shadow-emerald-500/10 hover:shadow-emerald-500/20",
  violet: "shadow-violet-500/10 hover:shadow-violet-500/20",
  amber: "shadow-amber-500/10 hover:shadow-amber-500/20",
  rose: "shadow-rose-500/10 hover:shadow-rose-500/20",
}

export const ContentCard = forwardRef<HTMLDivElement, ContentCardProps>(
  ({ 
    variant = "default", 
    size = "md", 
    hoverable = false,
    glow = false,
    glowColor = "blue",
    loading = false,
    disabled = false,
    className, 
    children, 
    ...props 
  }, ref) => {
    if (loading) {
      return (
        <div 
          ref={ref}
          className={cn(
            "rounded-xl animate-pulse bg-secondary/50",
            sizeStyles[size],
            className
          )}
          {...props}
        >
          <div className="h-4 w-3/4 bg-secondary rounded mb-2" />
          <div className="h-3 w-1/2 bg-secondary rounded" />
        </div>
      )
    }

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl transition-all duration-200",
          sizeStyles[size],
          variantStyles[variant],
          hoverable && "hover:scale-[1.01] hover:-translate-y-0.5",
          glow && `shadow-lg ${glowColors[glowColor]}`,
          disabled && "opacity-50 pointer-events-none",
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)
ContentCard.displayName = "ContentCard"

// =============================================================================
// ContentCardHeader - Header section for ContentCard
// =============================================================================

interface ContentCardHeaderProps {
  title: string
  description?: string
  icon?: IconName | LucideIcon
  iconColor?: string
  badge?: ReactNode
  actions?: ReactNode
  className?: string
}

export function ContentCardHeader({
  title,
  description,
  icon,
  iconColor = "text-foreground",
  badge,
  actions,
  className,
}: ContentCardHeaderProps) {
  const IconComponent = icon && typeof icon === "string" ? null : icon as LucideIcon | undefined

  return (
    <div className={cn("flex items-start justify-between gap-3", className)}>
      <div className="flex items-start gap-3 min-w-0">
        {icon && (
          <div className={cn(
            "flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/80 shrink-0",
            iconColor
          )}>
            {typeof icon === "string" ? (
              <Icon name={icon as IconName} size="lg" />
            ) : IconComponent ? (
              <IconComponent className="h-4 w-4" />
            ) : null}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-foreground truncate">{title}</h3>
            {badge}
          </div>
          {description && (
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{description}</p>
          )}
        </div>
      </div>
      {actions && (
        <div className="flex items-center gap-1 shrink-0">
          {actions}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// ContentCardBody - Main content section
// =============================================================================

interface ContentCardBodyProps {
  children: ReactNode
  className?: string
}

export function ContentCardBody({ children, className }: ContentCardBodyProps) {
  return (
    <div className={cn("mt-3", className)}>
      {children}
    </div>
  )
}

// =============================================================================
// ContentCardFooter - Footer section with actions or metadata
// =============================================================================

interface ContentCardFooterProps {
  children: ReactNode
  className?: string
  separator?: boolean
}

export function ContentCardFooter({ children, className, separator = true }: ContentCardFooterProps) {
  return (
    <div className={cn(
      "mt-4 flex items-center justify-between gap-3",
      separator && "pt-3 border-t border-border/50",
      className
    )}>
      {children}
    </div>
  )
}

// =============================================================================
// AnimatedContentCard - Motion-enabled version for lists
// =============================================================================

interface AnimatedContentCardProps extends ContentCardProps {
  index?: number
  layoutId?: string
}

export const AnimatedContentCard = forwardRef<HTMLDivElement, AnimatedContentCardProps>(
  ({ index = 0, layoutId, children, className, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        layoutId={layoutId}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2, delay: index * 0.05 }}
      >
        <ContentCard className={className} {...props}>
          {children}
        </ContentCard>
      </motion.div>
    )
  }
)
AnimatedContentCard.displayName = "AnimatedContentCard"

// =============================================================================
// MetricCard - Specialized card for displaying metrics/stats
// =============================================================================

interface MetricCardProps {
  label: string
  value: string | number
  change?: {
    value: string | number
    trend: "up" | "down" | "neutral"
  }
  icon?: IconName | LucideIcon
  variant?: "default" | "success" | "warning" | "error" | "info"
  size?: "sm" | "md" | "lg"
  className?: string
}

const metricVariantStyles = {
  default: "border-border",
  success: "border-emerald-500/20 bg-emerald-500/5",
  warning: "border-amber-500/20 bg-amber-500/5",
  error: "border-red-500/20 bg-red-500/5",
  info: "border-blue-500/20 bg-blue-500/5",
}

const metricValueColors = {
  default: "text-foreground",
  success: "text-emerald-500",
  warning: "text-amber-500",
  error: "text-red-500",
  info: "text-blue-500",
}

export function MetricCard({
  label,
  value,
  change,
  icon,
  variant = "default",
  size = "md",
  className,
}: MetricCardProps) {
  const IconComponent = icon && typeof icon === "string" ? null : icon as LucideIcon | undefined

  return (
    <div className={cn(
      "rounded-xl border p-3 relative overflow-hidden",
      metricVariantStyles[variant],
      size === "sm" && "p-2",
      size === "lg" && "p-4",
      className
    )}>
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-transparent to-secondary/30 pointer-events-none" />
      
      <div className="relative flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={cn(
            "text-2xl font-semibold mt-1",
            metricValueColors[variant],
            size === "sm" && "text-xl",
            size === "lg" && "text-3xl"
          )}>
            {value}
          </p>
          {change && (
            <div className={cn(
              "flex items-center gap-1 mt-1 text-xs",
              change.trend === "up" && "text-emerald-500",
              change.trend === "down" && "text-red-500",
              change.trend === "neutral" && "text-muted-foreground"
            )}>
              <Icon 
                name={change.trend === "up" ? "trendUp" : change.trend === "down" ? "trendDown" : "activity"} 
                size="xs" 
              />
              <span>{change.value}</span>
            </div>
          )}
        </div>
        {icon && (
          <div className="text-muted-foreground/30">
            {typeof icon === "string" ? (
              <Icon name={icon as IconName} size="2xl" />
            ) : IconComponent ? (
              <IconComponent className="h-8 w-8" />
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
