"use client"

import { cn } from "@/lib/utils"
import { EnvironmentBadge } from "./environment-badge"
import { Play, Workflow, Plug, Database, MoreHorizontal, Eye, RefreshCw, Trash2 } from "lucide-react"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"

type ContextEntity = "run" | "workflow" | "connector" | "source"
type Status = "success" | "failed" | "running" | "pending"

interface TimelineItemProps {
  id: string
  title: string
  timestamp: string
  environment: "production" | "staging"
  contextEntity: ContextEntity
  contextName: string
  status?: Status
  isActive?: boolean
  isLast?: boolean
  onClick?: () => void
  onView?: () => void
  onRetry?: () => void
  onDelete?: () => void
}

const entityIcons: Record<ContextEntity, typeof Play> = {
  run: Play,
  workflow: Workflow,
  connector: Plug,
  source: Database,
}

const statusConfig: Record<Status, { color: string; bgColor: string; pulseColor: string; label: string }> = {
  success: {
    color: "bg-emerald-500",
    bgColor: "bg-emerald-500/10",
    pulseColor: "bg-emerald-500/30",
    label: "Completed",
  },
  failed: {
    color: "bg-red-500",
    bgColor: "bg-red-500/10",
    pulseColor: "bg-red-500/30",
    label: "Failed",
  },
  running: {
    color: "bg-blue-500",
    bgColor: "bg-blue-500/10",
    pulseColor: "bg-blue-500/30",
    label: "Running",
  },
  pending: {
    color: "bg-amber-500",
    bgColor: "bg-amber-500/10",
    pulseColor: "bg-amber-500/30",
    label: "Pending",
  },
}

export function TimelineItem({
  title,
  timestamp,
  environment,
  contextEntity,
  contextName,
  status = "success",
  isActive = false,
  isLast = false,
  onClick,
  onView,
  onRetry,
  onDelete,
}: TimelineItemProps) {
  const [isHovered, setIsHovered] = useState(false)
  const Icon = entityIcons[contextEntity]
  const statusStyle = statusConfig[status]

  return (
    <div 
      className="relative flex gap-3"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Timeline Line & Node */}
      <div className="flex flex-col items-center">
        {/* Node */}
        <div className="relative z-10">
          <div
            className={cn(
              "flex h-3 w-3 items-center justify-center rounded-full transition-all duration-200",
              statusStyle.color,
              isActive && "ring-4 ring-offset-2 ring-offset-background",
              isActive && status === "success" && "ring-emerald-500/20",
              isActive && status === "failed" && "ring-red-500/20",
              isActive && status === "running" && "ring-blue-500/20",
              isActive && status === "pending" && "ring-amber-500/20"
            )}
          >
            {/* Pulse animation for running status */}
            {status === "running" && (
              <div className={cn("absolute inset-0 rounded-full animate-ping", statusStyle.pulseColor)} />
            )}
          </div>
        </div>
        
        {/* Connecting Line */}
        {!isLast && (
          <div className="w-px flex-1 bg-border/60 mt-1" />
        )}
      </div>

      {/* Content Card */}
      <motion.button
        onClick={onClick}
        whileHover={{ x: 2 }}
        transition={{ duration: 0.15 }}
        className={cn(
          "flex-1 mb-3 rounded-lg border text-left transition-all duration-200",
          isActive
            ? "border-border bg-secondary/80 shadow-sm"
            : "border-transparent hover:border-border/50 hover:bg-secondary/40"
        )}
      >
        <div className="p-3">
          {/* Header Row */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className={cn(
              "text-sm font-medium line-clamp-1 transition-colors",
              isActive ? "text-foreground" : "text-foreground/90"
            )}>
              {title}
            </h3>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] text-muted-foreground">{timestamp}</span>
              
              {/* Quick Actions - appear on hover */}
              <AnimatePresence>
                {isHovered && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ duration: 0.1 }}
                    className="flex items-center gap-0.5"
                  >
                    {onView && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onView(); }}
                        className="p-1 rounded hover:bg-secondary transition-colors"
                        title="View details"
                      >
                        <Eye className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                      </button>
                    )}
                    {onRetry && status === "failed" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onRetry(); }}
                        className="p-1 rounded hover:bg-secondary transition-colors"
                        title="Retry"
                      >
                        <RefreshCw className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                      </button>
                    )}
                    {onDelete && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                        className="p-1 rounded hover:bg-red-500/10 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="h-3 w-3 text-muted-foreground hover:text-red-400" />
                      </button>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Meta Row */}
          <div className="flex items-center gap-2 flex-wrap">
            <EnvironmentBadge environment={environment} />
            
            {/* Status Badge */}
            <div className={cn(
              "flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium",
              statusStyle.bgColor
            )}>
              <div className={cn("h-1 w-1 rounded-full", statusStyle.color)} />
              <span className={cn(
                status === "success" && "text-emerald-400",
                status === "failed" && "text-red-400",
                status === "running" && "text-blue-400",
                status === "pending" && "text-amber-400"
              )}>
                {statusStyle.label}
              </span>
            </div>

            {/* Context */}
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Icon className="h-3 w-3" />
              <span className="line-clamp-1">{contextName}</span>
            </div>
          </div>
        </div>
      </motion.button>
    </div>
  )
}

// Timeline Container Component
interface TimelineProps {
  children: React.ReactNode
  className?: string
}

export function Timeline({ children, className }: TimelineProps) {
  return (
    <div className={cn("relative", className)}>
      {children}
    </div>
  )
}
