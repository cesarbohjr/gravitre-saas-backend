"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Timeline, TimelineItem } from "@/components/gravitre/timeline-item"
import { MesonInsightsPanel } from "@/components/gravitre/ai-insights-panel"
import { AIProcessingStatus } from "@/components/gravitre/ai-processing-status"
import { AICommandInput } from "@/components/gravitre/ai-command-input"
import { SuggestedActions } from "@/components/gravitre/suggested-actions"
import { AIPresence } from "@/components/gravitre/ai-presence"
import { ModelSelector } from "@/components/gravitre/model-selector"
import { 
  ParticleField, 
  StatusBeacon
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { 
  Eye, Play, Search, FileCode, RefreshCw,
  CheckCircle, Sparkles, Loader2, ArrowRight,
  Activity
} from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { toast } from "sonner"

interface Task {
  id: string
  title: string
  timestamp: string
  environment: "production" | "staging"
  contextEntity: "run" | "workflow" | "connector" | "source"
  contextName: string
  status: "success" | "failed" | "running" | "pending"
}

interface FindingData {
  type: "analysis" | "discovery" | "summary"
  title: string
  content: string
  timestamp: string
}

interface ActionPlanStep {
  step: number
  title: string
  description: string
  status: "completed" | "current" | "pending"
}

interface SuggestedActionData {
  id: string
  title: string
  description: string
  icon: string
  environment: "production" | "staging"
  trustBadges: {
    confidenceScore: number
    guardrailStatus: "pass" | "warn" | "fail"
    tokenCount: number
    approvalRequired: boolean
  }
}

interface MetricsOverview {
  totalRuns?: number
  activeWorkflows?: number
  totalWorkflows?: number
}

// Flow steps for the progress indicator
const flowSteps = [
  { label: "Task", key: "task" },
  { label: "Analysis", key: "analysis" },
  { label: "Plan", key: "plan" },
  { label: "Confirm", key: "confirm" },
  { label: "Execute", key: "execute" },
]


const fallbackInsightSections = [
  {
    id: "summary",
    type: "summary" as const,
    title: "What Happened",
    content: "The customer sync (sync-customers-1234) stopped at step 3 of 5 while processing data. It successfully handled 12,450 records before the connection timed out after 30 seconds. This seems to happen during busy hours.",
  },
  {
    id: "reasoning",
    type: "reasoning" as const,
    title: "What I Checked",
    content: "I looked at the activity logs, past issues, and system performance to find out what went wrong.",
    steps: [
      { id: "r1", text: "Reviewed the timeline and found where it failed", isCompleted: true },
      { id: "r2", text: "Compared with similar runs from the past 30 days", isCompleted: true },
      { id: "r3", text: "Noticed failures happen mostly between 2-4 PM", isCompleted: true },
      { id: "r4", text: "Checked the Salesforce connection and found slowdowns", isCompleted: true },
      { id: "r5", text: "Looking at 3 similar issues from this week", isCompleted: false },
    ],
  },
  {
    id: "root-cause",
    type: "root-cause" as const,
    title: "Why It Failed",
    content: "The Salesforce connection slows down between 2-4 PM when there are too many requests at once. The 30-second wait time isn't long enough during these busy periods, so the data processing step fails while waiting for information.",
  },
  {
    id: "evidence",
    type: "evidence" as const,
    title: "What I Found",
    content: "Based on activity logs, performance data, and system records from the past 30 days.",
    evidence: [
      { id: "e1", source: "Activity Logs (sync-customers-1234)", relevance: "Shows timeout after 30.2 seconds" },
      { id: "e2", source: "Salesforce Connection Stats", relevance: "Slowdowns during afternoon hours" },
      { id: "e3", source: "Past Issues", relevance: "3 similar problems in the past week" },
    ],
  },
  {
    id: "actions",
    type: "actions" as const,
    title: "Suggested Fixes",
    content: "Here are the recommended changes to prevent this from happening again:",
    actions: [
      { id: "a1", label: "Wait longer (60 seconds) before timing out", priority: "high" as const },
      { id: "a2", label: "Automatically retry when things fail", priority: "high" as const },
      { id: "a3", label: "Run the sync before 2 PM to avoid busy hours", priority: "medium" as const },
      { id: "a4", label: "Add automatic pause when Salesforce is too slow", priority: "low" as const },
    ],
  },
]

const fallbackActionPlanSteps: ActionPlanStep[] = [
  {
    step: 1,
    title: "Check connection status",
    description: "Look at the Salesforce connection and recent activity",
    status: "completed",
  },
  {
    step: 2,
    title: "Review what happened",
    description: "Check the details of where things went wrong",
    status: "completed",
  },
  {
    step: 3,
    title: "Suggest a fix",
    description: "Create new settings with a longer wait time",
    status: "current",
  },
  {
    step: 4,
    title: "Execute remediation",
    description: "Apply fix and retry automation",
    status: "pending",
  },
]

const fallbackSuggestedActions: SuggestedActionData[] = [
  {
    id: "1",
    title: "Retry Automation with Extended Timeout",
    description: "Re-execute sync-customers automation with 60s timeout (increased from 30s)",
    icon: "RefreshCw",
    environment: "production",
    trustBadges: {
      confidenceScore: 87,
      guardrailStatus: "pass",
      tokenCount: 2450,
      approvalRequired: true,
    },
  },
  {
    id: "2",
    title: "Apply Connector Patch",
    description: "Update salesforce-api connector with retry logic for timeout errors",
    icon: "Zap",
    environment: "production",
    trustBadges: {
      confidenceScore: 72,
      guardrailStatus: "warn",
      tokenCount: 3200,
      approvalRequired: true,
    },
  },
]

const quickActions = [
  {
    title: "Inspect Connector",
    description: "View detailed connector status and connection logs",
    icon: Search,
    environment: "production" as const,
  },
  {
    title: "View Execution Details",
    description: "Open the full execution timeline and logs",
    icon: Eye,
    environment: "production" as const,
  },
  {
    title: "Draft Automation Fix",
    description: "Generate a proposed fix for the automation configuration",
    icon: FileCode,
    environment: "staging" as const,
    requiresAdmin: true,
  },
]

function toRelativeTime(value: string | null | undefined) {
  if (!value) return "just now"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "just now"
  const diffMinutes = Math.max(1, Math.floor((Date.now() - date.getTime()) / (1000 * 60)))
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function mapSessionStatusToTaskStatus(
  status: string | null | undefined
): Task["status"] {
  if (!status) return "pending"
  if (status === "completed" || status === "success") return "success"
  if (status === "failed" || status === "error") return "failed"
  if (status === "running" || status === "active" || status === "in_progress") return "running"
  return "pending"
}

function mapRunsToTasks(
  runs: Array<{
    id?: string
    workflowName?: string
    workflow_name?: string
    status?: string
    createdAt?: string
    created_at?: string
    workflowId?: string
    workflow_id?: string
    environment?: string
  }> | undefined
) {
  if (!runs || runs.length === 0) return []
  return runs.map((run, index) => {
    return {
      id: run.id ?? `run-${index}`,
      title: run.workflowName ?? run.workflow_name ?? "Workflow run",
      timestamp: toRelativeTime(run.createdAt ?? run.created_at),
      environment: run.environment === "staging" ? "staging" : "production",
      contextEntity: "run",
      contextName: run.workflowId ?? run.workflow_id ?? "unknown",
      status: mapSessionStatusToTaskStatus(run.status),
    } satisfies Task
  })
}



export default function OperatorPage() {
  const [activeTask, setActiveTask] = useState("")
  const [activeContext, setActiveContext] = useState("run-1234")
  const [taskInput, setTaskInput] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [executingAction, setExecutingAction] = useState<string | null>(null)
  const [currentFlowStep, setCurrentFlowStep] = useState<string>("task")
  const [selectedModel, setSelectedModel] = useState("auto")
  const [generatedPlan, setGeneratedPlan] = useState<{
    findings: FindingData[]
    steps: ActionPlanStep[]
    suggestedActions: SuggestedActionData[]
  } | null>(null)

  const { data: tasksData, error: tasksError, isLoading: tasksLoading } = useSWR<{ runs: Array<Record<string, unknown>> }>(
    "/api/runs?status=running,queued,needs_approval",
    fetcher,
    { revalidateOnFocus: false }
  )

  const { data: metricsData } = useSWR<MetricsOverview>(
    "/api/metrics/overview",
    fetcher,
    { revalidateOnFocus: false }
  )

  useEffect(() => {
    if (tasksError) {
      toast.error("Failed to load data")
    }
  }, [tasksError])

  const tasks = mapRunsToTasks(tasksData?.runs as Array<Record<string, unknown>>)
  useEffect(() => {
    if (!activeTask && tasks.length > 0) {
      setActiveTask(tasks[0].id)
    }
  }, [activeTask, tasks])
  const activeSystemCount = metricsData?.activeWorkflows ?? 12
  const insightSections = generatedPlan?.findings ?? fallbackInsightSections

  // Suggested actions for the secondary panel
  const suggestedActionsList = [
    {
      id: "action-1",
      title: "Increase timeout threshold to 60s",
      description: "Modify the transformation step timeout from 30s to 60s to handle peak hour latency",
      type: "immediate" as const,
      priority: "critical" as const,
      estimatedImpact: "Resolves 87% of timeout failures during peak hours",
      icon: "zap" as const,
    },
    {
      id: "action-2",
      title: "Add retry logic with exponential backoff",
      description: "Implement automatic retries with 1s, 2s, 4s delays before failing",
      type: "requires-approval" as const,
      priority: "high" as const,
      estimatedImpact: "Reduces transient failures by 65%",
      icon: "refresh" as const,
    },
    {
      id: "action-3",
      title: "Schedule sync before 2 PM UTC",
      description: "Move the daily sync window to avoid peak API traffic hours",
      type: "scheduled" as const,
      priority: "medium" as const,
      estimatedImpact: "Avoids 94% of rate limit issues",
      icon: "clock" as const,
    },
    {
      id: "action-4",
      title: "Enable circuit breaker pattern",
      description: "Add circuit breaker to Salesforce connector to prevent cascade failures",
      type: "requires-approval" as const,
      priority: "low" as const,
      estimatedImpact: "Improves system resilience during outages",
      icon: "shield" as const,
    },
  ]
  const actionPlanSteps = generatedPlan?.steps ?? fallbackActionPlanSteps
  const suggestedActions = generatedPlan?.suggestedActions ?? fallbackSuggestedActions

  // Get the active context label for display
  const getActiveContextLabel = () => {
    if (activeContext === "run-1234") return "execution · sync-customers-1234"
    if (activeContext === "workflow-sync") return "automation · sync-customers"
    if (activeContext === "connector-sf") return "connector · salesforce-api"
    if (activeContext === "source-pg") return "source · postgres-primary"
    return null
  }

  const activeContextLabel = getActiveContextLabel()
  const canCreateTask = activeTask && activeContext && taskInput.trim().length > 0

  if (tasksLoading) {
    return (
      <AppShell title="AI Operator">
        <div className="space-y-4 p-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      </AppShell>
    )
  }

  if (tasksError) {
    return (
      <AppShell title="AI Operator">
        <EmptyState
          icon={Activity}
          title="Error loading data"
          description="Failed to load data"
          variant="error"
        />
      </AppShell>
    )
  }

  if (!tasks.length) {
    return (
      <AppShell title="AI Operator">
        <EmptyState
          icon={Activity}
          title="No active tasks"
          description="Active runs will appear here when workflows execute."
        />
      </AppShell>
    )
  }

  const handleGeneratePlan = async () => {
    if (!canCreateTask) return
    setIsGenerating(true)
    setCurrentFlowStep("analysis")

    try {
      const response = await fetch(`/api/sessions/${activeTask}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: taskInput,
          context: { entityType: activeContext.split("-")[0], entityId: activeContext },
        }),
      })

      if (response.ok) {
        const data = await response.json()
        if (data.plan) {
          setGeneratedPlan({
            findings: data.plan.reasoning ?? fallbackInsightSections,
            steps: data.plan.steps ?? fallbackActionPlanSteps,
            suggestedActions: data.plan.proposals ?? fallbackSuggestedActions,
          })
          setCurrentFlowStep("plan")
        }
      }
    } catch {
      // Fall back to default data on error
      setCurrentFlowStep("plan")
    } finally {
      setIsGenerating(false)
      setTaskInput("")
    }
  }

  const handleCreateTask = async () => {
    try {
      const response = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New investigation" }),
      })
      if (response.ok) {
        const data = await response.json()
        if (data.session) {
          setActiveTask(data.session.id)
          setCurrentFlowStep("task")
          setGeneratedPlan(null)
        }
      }
    } catch {
      // Handle error silently
    }
  }

  const handleConfirmAction = () => {
    setCurrentFlowStep("confirm")
  }

  const handleExecuteAction = () => {
    setCurrentFlowStep("execute")
  }

  const handleSuggestedActionExecute = async (actionId: string) => {
    setExecutingAction(actionId)
    await new Promise((resolve) => setTimeout(resolve, 2000))
    setExecutingAction(null)
  }

  const handleSuggestedActionSchedule = (actionId: string) => {
    // Schedule action for later
  }

  const handleSuggestedActionDismiss = (actionId: string) => {
    // Dismiss action from list
  }

  return (
    <AppShell title="AI Operator">
      <div className="relative flex flex-col h-full overflow-hidden">
        {/* Subtle ambient background */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <div className="absolute inset-0 bg-gradient-to-br from-background via-background to-secondary/20" />
          <div className="absolute -top-40 -right-40 w-[500px] h-[500px] rounded-full bg-gradient-to-br from-violet-500/[0.03] to-transparent blur-3xl" />
        </div>

        {/* Main Content - Single Column Layout */}
        <div className="relative z-10 flex-1 flex flex-col overflow-hidden">
          {/* Clean Header with Stats */}
          <div className="shrink-0 border-b border-border px-6 py-5 bg-card/50 backdrop-blur-sm">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex items-center gap-4">
                <AIPresence 
                  isProcessing={isGenerating} 
                  isListening={Boolean(taskInput.trim())}
                />
              </div>
              <div className="flex items-center gap-3">
                {/* Model Selector - Premium, minimal */}
                <ModelSelector
                  value={selectedModel}
                  onChange={setSelectedModel}
                  inheritedFrom="workspace"
                  onResetToDefault={() => setSelectedModel("auto")}
                  showAdvanced
                  size="sm"
                />
                <div className="h-4 w-px bg-border" />
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <StatusBeacon status="active" size="sm" />
                  <span className="text-xs font-medium text-emerald-500">{activeSystemCount} systems</span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <Activity className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-xs font-medium text-blue-500">{tasks.length} active</span>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8 gap-2"
                  onClick={handleCreateTask}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  New Task
                </Button>
              </div>
            </div>
          </div>

          {/* Two Column Layout - Tasks + AI Workspace */}
          <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
            {/* Left: Task List (hidden on mobile, shown on desktop) */}
            <div className="hidden md:flex w-72 shrink-0 border-r border-border bg-card/30 flex-col">
              <div className="p-4 border-b border-border">
                <h2 className="text-sm font-semibold text-foreground mb-1">Tasks</h2>
                <p className="text-xs text-muted-foreground">Select a task to analyze</p>
              </div>
              <div className="flex-1 overflow-y-auto p-3 scrollbar-on-hover">
                <Timeline>
                  {tasks.map((task, index) => (
                    <TimelineItem
                      key={task.id}
                      {...task}
                      status={task.status}
                      isActive={task.id === activeTask}
                      isLast={index === tasks.length - 1}
                      onClick={() => {
                        setActiveTask(task.id)
                        setCurrentFlowStep("task")
                      }}
                      onView={() => {}}
                      onRetry={() => {}}
                      onDelete={() => {}}
                    />
                  ))}
                </Timeline>
              </div>
            </div>

            {/* Mobile Task Pills */}
            <div className="md:hidden border-b border-border bg-card/30 p-3 shrink-0">
              <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hidden">
                {tasks.map((task) => (
                  <button
                    key={task.id}
                    onClick={() => {
                      setActiveTask(task.id)
                      setCurrentFlowStep("task")
                    }}
                    className={`
                      flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-all
                      ${task.id === activeTask 
                        ? "bg-blue-500/20 text-blue-500 ring-1 ring-blue-500/30" 
                        : "bg-secondary text-muted-foreground hover:text-foreground"
                      }
                    `}
                  >
                    {task.title.length > 25 ? task.title.slice(0, 25) + "..." : task.title}
                  </button>
                ))}
              </div>
            </div>

            {/* Right: AI Workspace */}
            <div className="flex-1 overflow-y-auto scrollbar-on-hover min-h-0">
              <div className="p-4 md:p-6 max-w-3xl mx-auto">
              {/* 1. COMMAND INPUT (AI) - Premium */}
              <motion.section 
                className="mb-10"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <div className="relative">
                  {/* Glow behind input when focused */}
                  <motion.div 
                    className="absolute -inset-4 rounded-3xl bg-gradient-to-r from-blue-500/20 via-violet-500/20 to-blue-500/20 blur-2xl"
                    animate={{ opacity: taskInput.trim() ? 0.8 : 0.3 }}
                    transition={{ duration: 0.3 }}
                  />
                  <div className="relative">
                    <AICommandInput
                      value={taskInput}
                      onChange={setTaskInput}
                      onSubmit={handleGeneratePlan}
                      isProcessing={isGenerating}
                      disabled={!activeTask || !activeContext}
                      contextLabel={activeContextLabel || undefined}
                    />
                  </div>
                </div>
              </motion.section>

              {/* 2. LIVE AI PROCESSING STATE */}
              <AnimatePresence mode="wait">
                {isGenerating && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                  >
                    <div className="relative">
                      <ParticleField count={40} color="violet" className="opacity-40" />
                      <AIProcessingStatus 
                        isProcessing={isGenerating}
                        onComplete={() => setCurrentFlowStep("plan")}
                      />
                    </div>
                  </motion.section>
                )}
              </AnimatePresence>

              {/* 3. INSIGHT OUTPUT (PRIMARY) */}
              <AnimatePresence mode="wait">
                {!isGenerating && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ type: "spring", stiffness: 100 }}
                  >
                    <MesonInsightsPanel
                      confidence={87}
                      severity="high"
                      lastUpdated="2 minutes ago"
                      sections={insightSections}
                      isGenerating={isGenerating}
                    />
                  </motion.section>
                )}
              </AnimatePresence>

              {/* 4. SUGGESTED ACTIONS (SECONDARY) */}
              <AnimatePresence>
                {!isGenerating && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                  >
                    <SuggestedActions
                      actions={suggestedActionsList}
                      onExecute={handleSuggestedActionExecute}
                      onSchedule={handleSuggestedActionSchedule}
                      onDismiss={handleSuggestedActionDismiss}
                      isExecuting={executingAction}
                    />
                  </motion.section>
                )}
              </AnimatePresence>

              {/* Next Steps Section - Premium */}
              <AnimatePresence>
                {!isGenerating && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                  >
                    <div className="relative rounded-2xl border border-border bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm overflow-hidden shadow-xl shadow-black/5">
                      {/* Subtle corner accent */}
                      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/10 to-transparent rounded-bl-[100px]" />
                    <div className="border-b border-border px-5 py-3 bg-secondary/30">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <ArrowRight className="h-3 w-3" />
                        Execution Plan
                      </h3>
                    </div>
                    <div className="p-5">
                      <div className="space-y-4">
                        {actionPlanSteps.map((step, index) => (
                          <div key={step.step} className="flex items-start gap-4 group">
                            <div className="flex flex-col items-center">
                              <div className={`
                                flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-all
                                ${step.status === "completed" 
                                  ? "bg-success text-white" 
                                  : step.status === "current"
                                    ? "bg-info text-white ring-4 ring-info/20"
                                    : "bg-muted text-muted-foreground"
                                }
                              `}>
                                {step.status === "completed" ? (
                                  <CheckCircle className="h-4 w-4" />
                                ) : (
                                  step.step
                                )}
                              </div>
                              {index < actionPlanSteps.length - 1 && (
                                <div className={`w-0.5 h-8 mt-2 ${
                                  step.status === "completed" ? "bg-success/50" : "bg-border"
                                }`} />
                              )}
                            </div>
                            <div className="flex-1 min-w-0 pt-1">
                              <p className={`text-sm font-medium transition-colors ${
                                step.status === "completed" 
                                  ? "text-muted-foreground" 
                                  : step.status === "current"
                                    ? "text-foreground"
                                    : "text-muted-foreground"
                              }`}>
                                {step.title}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {step.description}
                              </p>
                              {step.status === "current" && (
                                <div className="flex items-center gap-2 mt-2">
                                  <Loader2 className="h-3 w-3 animate-spin text-info" />
                                  <span className="text-[10px] font-medium text-info">In Progress</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Action Buttons */}
                      <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-border">
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="h-9"
                          onClick={handleConfirmAction}
                          disabled={currentFlowStep === "task" || currentFlowStep === "execute"}
                        >
                          <Eye className="h-3.5 w-3.5 mr-2" />
                          Review Changes
                        </Button>
                        <Button 
                          size="sm" 
                          className="h-9 bg-gradient-to-r from-info to-info/80 hover:from-info/90 hover:to-info/70"
                          onClick={handleExecuteAction}
                          disabled={currentFlowStep === "task" || currentFlowStep === "execute"}
                        >
                          <Play className="h-3.5 w-3.5 mr-2" />
                          Approve & Execute
                        </Button>
                      </div>
                    </div>
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
