"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import {
  Target,
  TrendingUp,
  Clock,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Play,
  Pause,
  RotateCcw,
  ChevronRight,
  FileText,
  BarChart3,
  Zap,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react"

interface GoalProgress {
  current: number
  target: number
  unit: string
  trend: "up" | "down" | "stable"
  trendValue: string
}

interface GoalDeliverable {
  id: string
  name: string
  type: "report" | "campaign" | "summary" | "update"
  createdAt: string
  status: "complete" | "pending" | "draft"
}

interface GoalMonitoringPanelProps {
  goal?: {
    id: string
    name: string
    description: string
    status: "active" | "paused" | "completed" | "failed"
    successMetric: string
    progress: GoalProgress
    lastRun?: string
    nextRun?: string
    runCount: number
    deliverables: GoalDeliverable[]
  }
  className?: string
  onRunNow?: () => void
  onPause?: () => void
  onViewDeliverables?: () => void
}

const defaultGoal = {
  id: "goal-1",
  name: "Re-engage inactive leads",
  description: "Create personalized campaigns to re-engage leads with no activity in 90+ days",
  status: "active" as const,
  successMetric: "Email open rate > 20%",
  progress: {
    current: 312,
    target: 500,
    unit: "leads processed",
    trend: "up" as const,
    trendValue: "+15% this week",
  },
  lastRun: "2 hours ago",
  nextRun: "Tomorrow 9:00 AM",
  runCount: 12,
  deliverables: [
    { id: "d1", name: "Campaign Draft - Segment A", type: "campaign" as const, createdAt: "Today", status: "complete" as const },
    { id: "d2", name: "Campaign Draft - Segment B", type: "campaign" as const, createdAt: "Today", status: "draft" as const },
    { id: "d3", name: "Weekly Performance Report", type: "report" as const, createdAt: "Yesterday", status: "complete" as const },
  ],
}

export function GoalMonitoringPanel({
  goal = defaultGoal,
  className,
  onRunNow,
  onPause,
  onViewDeliverables,
}: GoalMonitoringPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  
  const progressPercent = Math.round((goal.progress.current / goal.progress.target) * 100)
  
  const getStatusColor = (status: typeof goal.status) => {
    switch (status) {
      case "active": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      case "paused": return "bg-amber-500/20 text-amber-400 border-amber-500/30"
      case "completed": return "bg-blue-500/20 text-blue-400 border-blue-500/30"
      case "failed": return "bg-red-500/20 text-red-400 border-red-500/30"
    }
  }

  const getDeliverableIcon = (type: GoalDeliverable["type"]) => {
    switch (type) {
      case "report": return BarChart3
      case "campaign": return Zap
      case "summary": return FileText
      case "update": return RefreshCw
    }
  }

  return (
    <motion.div
      layout
      className={cn(
        "rounded-xl border border-violet-500/20 bg-gradient-to-br from-violet-500/5 to-purple-500/5 overflow-hidden",
        className
      )}
    >
      {/* Header */}
      <div 
        className="p-4 flex items-start gap-3 cursor-pointer hover:bg-violet-500/5 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/20 border border-violet-500/30">
          <Target className="h-5 w-5 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-foreground truncate">{goal.name}</h3>
            <Badge variant="outline" className={cn("text-[10px] py-0 h-5", getStatusColor(goal.status))}>
              {goal.status}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-1">{goal.description}</p>
        </div>
        <ChevronRight className={cn(
          "h-5 w-5 text-muted-foreground shrink-0 transition-transform",
          isExpanded && "rotate-90"
        )} />
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="px-4 pb-4 space-y-4"
        >
          {/* Progress */}
          <div className="p-3 rounded-lg bg-secondary/30 border border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground">Progress</span>
              <div className={cn(
                "flex items-center gap-1 text-xs",
                goal.progress.trend === "up" ? "text-emerald-400" :
                goal.progress.trend === "down" ? "text-red-400" :
                "text-muted-foreground"
              )}>
                {goal.progress.trend === "up" && <TrendingUp className="h-3 w-3" />}
                {goal.progress.trendValue}
              </div>
            </div>
            <div className="flex items-end gap-2 mb-2">
              <span className="text-2xl font-bold text-foreground">{goal.progress.current}</span>
              <span className="text-sm text-muted-foreground mb-0.5">/ {goal.progress.target} {goal.progress.unit}</span>
            </div>
            <Progress value={progressPercent} className="h-2" />
          </div>

          {/* Success Metric */}
          <div className="flex items-center gap-2 p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
            <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <span className="text-xs text-muted-foreground">Success Metric: </span>
              <span className="text-xs text-emerald-400 font-medium">{goal.successMetric}</span>
            </div>
          </div>

          {/* Run info */}
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 rounded-lg bg-secondary/30 border border-border">
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
                <Clock className="h-3 w-3" />
                Last Run
              </div>
              <span className="text-sm font-medium text-foreground">{goal.lastRun || "Never"}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-secondary/30 border border-border">
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mb-1">
                <Calendar className="h-3 w-3" />
                Next Run
              </div>
              <span className="text-sm font-medium text-foreground">{goal.nextRun || "Not scheduled"}</span>
            </div>
          </div>

          {/* Recent Deliverables */}
          {goal.deliverables.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-muted-foreground">Recent Deliverables</span>
                <button 
                  onClick={onViewDeliverables}
                  className="text-[10px] text-violet-400 hover:text-violet-300 flex items-center gap-0.5"
                >
                  View all
                  <ArrowUpRight className="h-3 w-3" />
                </button>
              </div>
              <div className="space-y-1.5">
                {goal.deliverables.slice(0, 3).map((deliverable) => {
                  const Icon = getDeliverableIcon(deliverable.type)
                  return (
                    <div
                      key={deliverable.id}
                      className="flex items-center gap-2 p-2 rounded-lg bg-secondary/30 border border-border hover:bg-secondary/50 transition-colors cursor-pointer"
                    >
                      <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                      <div className="flex-1 min-w-0">
                        <span className="text-xs font-medium text-foreground truncate block">{deliverable.name}</span>
                        <span className="text-[10px] text-muted-foreground">{deliverable.createdAt}</span>
                      </div>
                      <Badge 
                        variant="outline" 
                        className={cn(
                          "text-[9px] py-0 h-4",
                          deliverable.status === "complete" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                          deliverable.status === "draft" ? "bg-amber-500/10 text-amber-400 border-amber-500/30" :
                          "bg-blue-500/10 text-blue-400 border-blue-500/30"
                        )}
                      >
                        {deliverable.status}
                      </Badge>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t border-border">
            <Button
              size="sm"
              variant="default"
              onClick={onRunNow}
              className="flex-1 h-8 gap-1.5 text-xs bg-violet-600 hover:bg-violet-700"
            >
              <Play className="h-3.5 w-3.5" />
              Run Now
            </Button>
            {goal.status === "active" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={onPause}
                className="h-8 gap-1.5 text-xs"
              >
                <Pause className="h-3.5 w-3.5" />
                Pause
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={onPause}
                className="h-8 gap-1.5 text-xs"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Resume
              </Button>
            )}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}
