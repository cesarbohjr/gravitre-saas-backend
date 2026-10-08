"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Zap, 
  Play, 
  RefreshCw, 
  Clock, 
  Shield, 
  AlertTriangle,
  ChevronRight,
  Check,
  Loader2,
  ArrowUpRight,
  X
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "sonner"

interface Action {
  id: string
  title: string
  description: string
  type: "immediate" | "scheduled" | "requires-approval"
  priority: "critical" | "high" | "medium" | "low"
  estimatedImpact?: string
  icon?: "zap" | "refresh" | "play" | "shield" | "clock"
}

interface SuggestedActionsProps {
  actions: Action[]
  onExecute?: (actionId: string) => void
  onSchedule?: (actionId: string) => void
  onDismiss?: (actionId: string) => void
  isExecuting?: string | null
}

const iconMap = {
  zap: Zap,
  refresh: RefreshCw,
  play: Play,
  shield: Shield,
  clock: Clock,
}

const priorityConfig = {
  critical: {
    bg: "bg-destructive/10",
    border: "border-destructive/30",
    text: "text-danger-text",
    badge: "bg-destructive/20 text-danger-text",
    glow: "shadow-destructive/20",
  },
  high: {
    bg: "bg-warning/10",
    border: "border-warning/30",
    text: "text-warning-text",
    badge: "bg-warning/20 text-warning-text",
    glow: "shadow-warning/20",
  },
  medium: {
    bg: "bg-info/10",
    border: "border-info/30",
    text: "text-info",
    badge: "bg-info/20 text-info",
    glow: "shadow-info/20",
  },
  low: {
    bg: "bg-muted-foreground/10",
    border: "border-muted-foreground/30",
    text: "text-muted-foreground",
    badge: "bg-muted-foreground/20 text-muted-foreground",
    glow: "shadow-muted-foreground/20",
  },
}

const typeLabels = {
  "immediate": "Run Now",
  "scheduled": "Schedule",
  "requires-approval": "Needs Approval",
}

export function SuggestedActions({
  actions,
  onExecute,
  onSchedule,
  onDismiss,
  isExecuting,
}: SuggestedActionsProps) {
  const [expandedAction, setExpandedAction] = useState<string | null>(null)
  const [completedActions, setCompletedActions] = useState<Set<string>>(new Set())
  const [showViewAll, setShowViewAll] = useState(false)
  const [isExecutingAll, setIsExecutingAll] = useState(false)
  const [executingActions, setExecutingActions] = useState<Set<string>>(new Set())

  const handleExecute = async (actionId: string) => {
    setExecutingActions(prev => new Set([...prev, actionId]))
    onExecute?.(actionId)
    // Simulate completion
    await new Promise((resolve) => setTimeout(resolve, 2000))
    setExecutingActions(prev => {
      const next = new Set(prev)
      next.delete(actionId)
      return next
    })
    setCompletedActions((prev) => new Set([...prev, actionId]))
  }

  const handleExecuteAll = async () => {
    const pendingActions = actions.filter(a => !completedActions.has(a.id))
    if (pendingActions.length === 0) {
      toast.info("All actions have already been executed")
      return
    }
    
    setIsExecutingAll(true)
    toast.info(`Executing ${pendingActions.length} actions...`)
    
    // Execute actions sequentially by priority
    const sortedActions = [...pendingActions].sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      return priorityOrder[a.priority] - priorityOrder[b.priority]
    })
    
    for (const action of sortedActions) {
      await handleExecute(action.id)
    }
    
    setIsExecutingAll(false)
    toast.success("All actions executed successfully", {
      description: `${pendingActions.length} actions completed`
    })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card/50 backdrop-blur-sm overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3 bg-secondary/30">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-warning/20">
            <Zap className="h-3.5 w-3.5 text-warning-text" />
          </div>
          <h3 className="text-sm font-semibold text-foreground">Suggested actions</h3>
          <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            {actions.length} available
          </span>
        </div>
        <Button 
          variant="ghost" 
          size="sm" 
          className="h-7 text-xs gap-1"
          onClick={() => setShowViewAll(true)}
        >
          View all
          <ArrowUpRight className="h-3 w-3" />
        </Button>
      </div>

      {/* Actions List */}
      <div className="divide-y divide-border">
        <AnimatePresence mode="popLayout">
          {actions.map((action, index) => {
            const IconComponent = iconMap[action.icon || "zap"]
            const config = priorityConfig[action.priority]
            const isCompleted = completedActions.has(action.id)
            const isCurrentlyExecuting = isExecuting === action.id
            const isExpanded = expandedAction === action.id

            return (
              <motion.div
                key={action.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20, height: 0 }}
                transition={{ delay: index * 0.05 }}
                className={`relative ${isCompleted ? "opacity-60" : ""}`}
              >
                {/* Priority indicator line */}
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${config.bg}`} />
                
                <div 
                  className={`p-4 pl-5 transition-colors ${isExpanded ? "bg-secondary/30" : "hover:bg-secondary/20"}`}
                >
                  <div className="flex items-start gap-3">
                    {/* Icon */}
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${config.bg} ${config.border} border`}>
                      {isCompleted ? (
                        <Check className={`h-4 w-4 ${config.text}`} />
                      ) : isCurrentlyExecuting ? (
                        <Loader2 className={`h-4 w-4 ${config.text} animate-spin`} />
                      ) : (
                        <IconComponent className={`h-4 w-4 ${config.text}`} />
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className={`text-sm font-medium ${isCompleted ? "line-through text-muted-foreground" : "text-foreground"}`}>
                          {action.title}
                        </h4>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${config.badge}`}>
                          {action.priority}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {action.description}
                      </p>
                      
                      {/* Expanded Details */}
                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mt-3 pt-3 border-t border-border"
                          >
                            {action.estimatedImpact && (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
                                <AlertTriangle className="h-3 w-3" />
                                <span>Estimated Impact: {action.estimatedImpact}</span>
                              </div>
                            )}
                            <div className="flex items-center gap-2">
                              <Button 
                                size="sm" 
                                className="h-7 text-xs gap-1"
                                onClick={() => handleExecute(action.id)}
                                disabled={isCompleted || isCurrentlyExecuting}
                              >
                                {isCurrentlyExecuting ? (
                                  <>
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    Executing...
                                  </>
                                ) : isCompleted ? (
                                  <>
                                    <Check className="h-3 w-3" />
                                    Completed
                                  </>
                                ) : (
                                  <>
                                    <Play className="h-3 w-3" />
                                    {typeLabels[action.type]}
                                  </>
                                )}
                              </Button>
                              {action.type === "scheduled" && !isCompleted && (
                                <Button 
                                  variant="outline" 
                                  size="sm" 
                                  className="h-7 text-xs gap-1"
                                  onClick={() => onSchedule?.(action.id)}
                                >
                                  <Clock className="h-3 w-3" />
                                  Schedule
                                </Button>
                              )}
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-7 text-xs text-muted-foreground"
                                onClick={() => onDismiss?.(action.id)}
                              >
                                Dismiss
                              </Button>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Expand/Collapse Button */}
                    <button
                      onClick={() => setExpandedAction(isExpanded ? null : action.id)}
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
                    >
                      <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`} />
                    </button>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>

      {/* Quick Execute Footer */}
      <div className="flex items-center justify-between border-t border-border px-4 py-3 bg-secondary/20">
        <p className="text-[10px] text-muted-foreground">
          Actions are staged for review before execution
        </p>
        <Button 
          variant="outline" 
          size="sm" 
          className="h-7 text-xs gap-1"
          onClick={handleExecuteAll}
          disabled={isExecutingAll || completedActions.size === actions.length}
        >
          {isExecutingAll ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              Executing...
            </>
          ) : completedActions.size === actions.length ? (
            <>
              <Check className="h-3 w-3" />
              All done
            </>
          ) : (
            <>
              Execute all
              <ChevronRight className="h-3 w-3" />
            </>
          )}
        </Button>
      </div>

      {/* View All Dialog */}
      <Dialog open={showViewAll} onOpenChange={setShowViewAll}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-warning/20">
                <Zap className="h-4 w-4 text-warning-text" />
              </div>
              All suggested actions
            </DialogTitle>
            <DialogDescription>
              Review and execute all recommended actions to resolve the issue.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            {actions.map((action) => {
              const IconComponent = iconMap[action.icon || "zap"]
              const config = priorityConfig[action.priority]
              const isCompleted = completedActions.has(action.id)
              const isCurrentlyExecuting = executingActions.has(action.id)

              return (
                <div 
                  key={action.id}
                  className={`relative rounded-lg border ${config.border} ${config.bg} p-4 ${isCompleted ? "opacity-60" : ""}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${config.bg} border ${config.border}`}>
                      {isCompleted ? (
                        <Check className={`h-5 w-5 ${config.text}`} />
                      ) : isCurrentlyExecuting ? (
                        <Loader2 className={`h-5 w-5 ${config.text} animate-spin`} />
                      ) : (
                        <IconComponent className={`h-5 w-5 ${config.text}`} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className={`text-sm font-medium ${isCompleted ? "line-through text-muted-foreground" : "text-foreground"}`}>
                          {action.title}
                        </h4>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${config.badge}`}>
                          {action.priority}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {action.description}
                      </p>
                      {action.estimatedImpact && (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                          <AlertTriangle className="h-3 w-3" />
                          Impact: {action.estimatedImpact}
                        </div>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant={isCompleted ? "outline" : "default"}
                      className="h-8 text-xs gap-1.5 shrink-0"
                      onClick={() => handleExecute(action.id)}
                      disabled={isCompleted || isCurrentlyExecuting}
                    >
                      {isCurrentlyExecuting ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Running
                        </>
                      ) : isCompleted ? (
                        <>
                          <Check className="h-3 w-3" />
                          Done
                        </>
                      ) : (
                        <>
                          <Play className="h-3 w-3" />
                          Execute
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between items-center pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              {completedActions.size} of {actions.length} completed
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setShowViewAll(false)}>
                Close
              </Button>
              <Button 
                onClick={handleExecuteAll}
                disabled={isExecutingAll || completedActions.size === actions.length}
                className="gap-1.5"
              >
                {isExecutingAll ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Execute all remaining
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  )
}
