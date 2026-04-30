"use client"

import { cn } from "@/lib/utils"
import { EnvironmentBadge } from "./environment-badge"
import { Play, Workflow, Plug, Database, MoreHorizontal, Eye, RefreshCw, Trash2, CheckCircle, AlertCircle, Clock, Loader2 } from "lucide-react"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { timing, easing } from "@/lib/animations"

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

const statusConfig: Record<Status, { 
  color: string
  bgColor: string
  pulseColor: string
  label: string
  icon: typeof CheckCircle
  glowColor: string
}> = {
  success: {
    color: "bg-emerald-500",
    bgColor: "bg-emerald-500/10",
    pulseColor: "bg-emerald-500/30",
    label: "Completed",
    icon: CheckCircle,
    glowColor: "shadow-emerald-500/20",
  },
  failed: {
    color: "bg-red-500",
    bgColor: "bg-red-500/10",
    pulseColor: "bg-red-500/30",
    label: "Failed",
    icon: AlertCircle,
    glowColor: "shadow-red-500/20",
  },
  running: {
    color: "bg-blue-500",
    bgColor: "bg-blue-500/10",
    pulseColor: "bg-blue-500/30",
    label: "Running",
    icon: Loader2,
    glowColor: "shadow-blue-500/20",
  },
  pending: {
    color: "bg-amber-500",
    bgColor: "bg-amber-500/10",
    pulseColor: "bg-amber-500/30",
    label: "Pending",
    icon: Clock,
    glowColor: "shadow-amber-500/20",
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
    <motion.div 
      className="relative flex gap-3"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: timing.ui, ease: easing.smooth as number[] }}
    >
      {/* Timeline Line & Node */}
      <div className="flex flex-col items-center">
        {/* Node */}
        <motion.div 
          className="relative z-10"
          animate={isActive ? { scale: 1.1 } : { scale: 1 }}
          transition={{ duration: timing.micro }}
        >
          <motion.div
            className={cn(
              "flex h-3.5 w-3.5 items-center justify-center rounded-full transition-all duration-200",
              statusStyle.color,
              isActive && "ring-4 ring-offset-2 ring-offset-background shadow-lg",
              isActive && statusStyle.glowColor,
              isActive && status === "success" && "ring-emerald-500/30",
              isActive && status === "failed" && "ring-red-500/30",
              isActive && status === "running" && "ring-blue-500/30",
              isActive && status === "pending" && "ring-amber-500/30"
            )}
            whileHover={{ scale: 1.2 }}
            transition={{ duration: timing.micro }}
          >
            {/* Pulse animation for running status */}
            {status === "running" && (
              <>
                <motion.div 
                  className={cn("absolute inset-0 rounded-full", statusStyle.pulseColor)}
                  animate={{ scale: [1, 1.8, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                />
                <motion.div 
                  className={cn("absolute inset-0 rounded-full", statusStyle.pulseColor)}
                  animate={{ scale: [1, 2.2, 1], opacity: [0.4, 0, 0.4] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.3 }}
                />
              </>
            )}
            {/* Subtle pulse for failed status */}
            {status === "failed" && (
              <motion.div 
                className={cn("absolute inset-0 rounded-full", statusStyle.pulseColor)}
                animate={{ opacity: [0.3, 0.6, 0.3] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              />
            )}
          </motion.div>
        </motion.div>
        
        {/* Connecting Line */}
        {!isLast && (
          <motion.div 
            className="w-px flex-1 mt-1"
            initial={{ scaleY: 0, originY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: timing.ui, delay: 0.1 }}
          >
            <div className={cn(
              "w-full h-full",
              isActive ? "bg-gradient-to-b from-border to-border/30" : "bg-border/60"
            )} />
          </motion.div>
        )}
      </div>

      {/* Content Card */}
      <motion.button
        onClick={onClick}
        whileHover={{ x: 4, scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        transition={{ duration: timing.micro }}
        className={cn(
          "flex-1 mb-3 rounded-lg border text-left transition-all duration-200",
          isActive
            ? "border-border bg-secondary/80 shadow-md"
            : "border-transparent hover:border-border/50 hover:bg-secondary/40 hover:shadow-sm"
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
