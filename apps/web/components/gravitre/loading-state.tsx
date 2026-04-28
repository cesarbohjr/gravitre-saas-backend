"use client"

import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

// =============================================================================
// LoadingSpinner - Centered spinner for page/section loading
// =============================================================================

interface LoadingSpinnerProps {
  /** Size variant */
  size?: "sm" | "md" | "lg"
  /** Optional label text */
  label?: string
  /** Additional className */
  className?: string
}

const spinnerSizes = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
}

const containerSizes = {
  sm: "py-8",
  md: "py-12",
  lg: "py-16",
}

export function LoadingSpinner({
  size = "md",
  label,
  className,
}: LoadingSpinnerProps) {
  return (
    <div className={cn(
      "flex flex-col items-center justify-center gap-3",
      containerSizes[size],
      className
    )}>
      <Spinner className={spinnerSizes[size]} />
      {label && (
        <p className="text-sm text-muted-foreground animate-pulse">{label}</p>
      )}
    </div>
  )
}

// =============================================================================
// CardSkeleton - Skeleton loading state for cards
// =============================================================================

interface CardSkeletonProps {
  /** Show icon placeholder */
  showIcon?: boolean
  /** Show badge placeholders */
  showBadges?: boolean
  /** Show footer section */
  showFooter?: boolean
  /** Number of description lines */
  lines?: 1 | 2 | 3
  /** Additional className */
  className?: string
}

export function CardSkeleton({
  showIcon = true,
  showBadges = true,
  showFooter = false,
  lines = 2,
  className,
}: CardSkeletonProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={cn(
        "rounded-xl border border-border bg-card p-4 space-y-3",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1">
          {showIcon && (
            <Skeleton className="h-9 w-9 rounded-lg shrink-0" />
          )}
          <div className="space-y-2 flex-1">
            <Skeleton className="h-4 w-2/3" />
            {lines >= 1 && <Skeleton className="h-3 w-full" />}
            {lines >= 2 && <Skeleton className="h-3 w-4/5" />}
            {lines >= 3 && <Skeleton className="h-3 w-1/2" />}
          </div>
        </div>
        <Skeleton className="h-6 w-12 rounded" />
      </div>

      {/* Badges */}
      {showBadges && (
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-16 rounded" />
          <Skeleton className="h-5 w-20 rounded" />
        </div>
      )}

      {/* Footer */}
      {showFooter && (
        <div className="flex items-center justify-between pt-3 border-t border-border/50">
          <div className="flex items-center gap-4">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-20" />
          </div>
          <Skeleton className="h-4 w-14" />
        </div>
      )}
    </motion.div>
  )
}

// =============================================================================
// TableSkeleton - Skeleton loading state for data tables
// =============================================================================

interface TableSkeletonProps {
  /** Number of rows to show */
  rows?: number
  /** Number of columns */
  columns?: number
  /** Show header row */
  showHeader?: boolean
  /** Additional className */
  className?: string
}

export function TableSkeleton({
  rows = 5,
  columns = 4,
  showHeader = true,
  className,
}: TableSkeletonProps) {
  return (
    <div className={cn("rounded-xl border border-border overflow-hidden", className)}>
      {/* Header */}
      {showHeader && (
        <div className="flex items-center gap-4 bg-secondary/30 px-4 py-3 border-b border-border">
          {Array.from({ length: columns }).map((_, i) => (
            <Skeleton 
              key={i} 
              className={cn(
                "h-4",
                i === 0 ? "w-1/4" : i === columns - 1 ? "w-16" : "w-20"
              )} 
            />
          ))}
        </div>
      )}

      {/* Rows */}
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <motion.div
            key={rowIndex}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: rowIndex * 0.05 }}
            className="flex items-center gap-4 px-4 py-3"
          >
            {Array.from({ length: columns }).map((_, colIndex) => (
              <Skeleton 
                key={colIndex} 
                className={cn(
                  "h-4",
                  colIndex === 0 ? "w-1/3" : colIndex === columns - 1 ? "w-12" : "w-24"
                )} 
              />
            ))}
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// ListSkeleton - Skeleton loading state for lists
// =============================================================================

interface ListSkeletonProps {
  /** Number of items to show */
  items?: number
  /** Show avatars */
  showAvatar?: boolean
  /** Show timestamps */
  showTimestamp?: boolean
  /** Additional className */
  className?: string
}

export function ListSkeleton({
  items = 4,
  showAvatar = false,
  showTimestamp = true,
  className,
}: ListSkeletonProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: items }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
          className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card"
        >
          {showAvatar && (
            <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          )}
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          {showTimestamp && (
            <Skeleton className="h-3 w-12" />
          )}
        </motion.div>
      ))}
    </div>
  )
}

// =============================================================================
// PageSkeleton - Full page loading skeleton
// =============================================================================

interface PageSkeletonProps {
  /** Show header section */
  showHeader?: boolean
  /** Show stats section */
  showStats?: boolean
  /** Show sidebar */
  showSidebar?: boolean
  /** Content type */
  contentType?: "cards" | "table" | "list"
  /** Additional className */
  className?: string
}

export function PageSkeleton({
  showHeader = true,
  showStats = false,
  showSidebar = false,
  contentType = "cards",
  className,
}: PageSkeletonProps) {
  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      {showHeader && (
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
          <Skeleton className="h-9 w-32" />
        </div>
      )}

      {/* Stats */}
      {showStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4">
              <Skeleton className="h-3 w-20 mb-2" />
              <Skeleton className="h-7 w-16" />
            </div>
          ))}
        </div>
      )}

      {/* Content */}
      <div className={cn("flex gap-6", showSidebar && "flex-col lg:flex-row")}>
        {/* Main content */}
        <div className={cn("flex-1", showSidebar && "lg:w-2/3")}>
          {contentType === "cards" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          )}
          {contentType === "table" && <TableSkeleton />}
          {contentType === "list" && <ListSkeleton />}
        </div>

        {/* Sidebar */}
        {showSidebar && (
          <div className="lg:w-1/3 space-y-4">
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <Skeleton className="h-5 w-20" />
              <ListSkeleton items={3} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
