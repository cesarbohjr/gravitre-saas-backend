"use client"

import { type ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { type LucideIcon, Inbox, Search, FileQuestion, AlertCircle, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"

interface EmptyStateProps {
  /** Icon to display */
  icon?: LucideIcon
  /** Title text */
  title: string
  /** Description text */
  description?: string
  /** Visual variant */
  variant?: "default" | "search" | "error" | "ai"
  /** Size variant */
  size?: "sm" | "md" | "lg"
  /** Primary action button */
  action?: {
    label: string
    onClick: () => void
    variant?: "default" | "outline" | "ghost"
  }
  /** Secondary action button */
  secondaryAction?: {
    label: string
    onClick: () => void
  }
  /** Custom content below description */
  children?: ReactNode
  /** Additional className */
  className?: string
}

const variantIcons: Record<string, LucideIcon> = {
  default: Inbox,
  search: Search,
  error: AlertCircle,
  ai: Sparkles,
}

const variantStyles = {
  default: {
    iconBg: "bg-secondary/80",
    iconColor: "text-muted-foreground",
  },
  search: {
    iconBg: "bg-blue-500/10",
    iconColor: "text-blue-500",
  },
  error: {
    iconBg: "bg-red-500/10",
    iconColor: "text-red-500",
  },
  ai: {
    iconBg: "bg-violet-500/10",
    iconColor: "text-violet-500",
  },
}

const sizeStyles = {
  sm: {
    container: "py-8",
    iconContainer: "w-10 h-10",
    icon: "h-5 w-5",
    title: "text-sm",
    description: "text-xs",
  },
  md: {
    container: "py-12",
    iconContainer: "w-12 h-12",
    icon: "h-6 w-6",
    title: "text-base",
    description: "text-sm",
  },
  lg: {
    container: "py-16",
    iconContainer: "w-16 h-16",
    icon: "h-8 w-8",
    title: "text-lg",
    description: "text-base",
  },
}

export function EmptyState({
  icon,
  title,
  description,
  variant = "default",
  size = "md",
  action,
  secondaryAction,
  children,
  className,
}: EmptyStateProps) {
  const Icon = icon || variantIcons[variant]
  const styles = variantStyles[variant]
  const sizes = sizeStyles[size]

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex flex-col items-center justify-center text-center",
        sizes.container,
        className
      )}
    >
      {/* Icon */}
      <motion.div
        initial={{ scale: 0.8 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.1 }}
        className={cn(
          "flex items-center justify-center rounded-xl mb-4",
          sizes.iconContainer,
          styles.iconBg
        )}
      >
        <Icon className={cn(sizes.icon, styles.iconColor)} />
      </motion.div>

      {/* Title */}
      <h3 className={cn("font-medium text-foreground", sizes.title)}>
        {title}
      </h3>

      {/* Description */}
      {description && (
        <p className={cn("text-muted-foreground mt-1 max-w-sm", sizes.description)}>
          {description}
        </p>
      )}

      {/* Custom content */}
      {children && (
        <div className="mt-4">
          {children}
        </div>
      )}

      {/* Actions */}
      {(action || secondaryAction) && (
        <div className="flex items-center gap-2 mt-6">
          {action && (
            <Button
              variant={action.variant || "default"}
              size={size === "sm" ? "sm" : "default"}
              onClick={action.onClick}
            >
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button
              variant="ghost"
              size={size === "sm" ? "sm" : "default"}
              onClick={secondaryAction.onClick}
            >
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </motion.div>
  )
}

// Preset empty states for common use cases
export function NoResultsState({ 
  query, 
  onClear 
}: { 
  query?: string
  onClear?: () => void 
}) {
  return (
    <EmptyState
      variant="search"
      title={query ? `No results for "${query}"` : "No results found"}
      description="Try adjusting your search or filters to find what you're looking for."
      action={onClear ? { label: "Clear search", onClick: onClear, variant: "outline" } : undefined}
    />
  )
}

export function NoDataState({ 
  itemName = "items",
  onCreate 
}: { 
  itemName?: string
  onCreate?: () => void 
}) {
  return (
    <EmptyState
      title={`No ${itemName} yet`}
      description={`Create your first ${itemName.slice(0, -1)} to get started.`}
      action={onCreate ? { label: `Create ${itemName.slice(0, -1)}`, onClick: onCreate } : undefined}
    />
  )
}

export function ErrorState({ 
  title = "Something went wrong",
  description = "We couldn't load this content. Please try again.",
  onRetry 
}: { 
  title?: string
  description?: string
  onRetry?: () => void 
}) {
  return (
    <EmptyState
      variant="error"
      title={title}
      description={description}
      action={onRetry ? { label: "Try again", onClick: onRetry, variant: "outline" } : undefined}
    />
  )
}
