"use client"

import { useEffect, useState, useCallback } from "react"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Timeline, TimelineItem } from "@/components/gravitre/timeline-item"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { cn } from "@/lib/utils"
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
  Activity, X, Trash2, AlertCircle, RotateCcw
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useAsyncJob, type AgentJob, type AgentJobResult } from "@/hooks/use-async-job"

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

type OperatorSessionPayload = {
  id?: string
  title?: string
  status?: string
  environment?: string
  current_task?: string
  currentTask?: string
  created_at?: string
  createdAt?: string
  context_entity_type?: string
  contextEntityType?: string
  context_entity_id?: string
  contextEntityId?: string
}

type OperatorSessionsResponse = {
  sessions?: OperatorSessionPayload[]
  activities?: OperatorSessionPayload[]
}

// Flow steps for the progress indicator
const flowSteps = [
  { label: "Task", key: "task" },
  { label: "Analysis", key: "analysis" },
  { label: "Plan", key: "plan" },
  { label: "Confirm", key: "confirm" },
  { label: "Execute", key: "execute" },
]

const fallbackTasks: Task[] = [
  {
    id: "1",
    title: "Looking into failed customer sync",
    timestamp: "2m ago",
    environment: "production",
    contextEntity: "run",
    contextName: "sync-customers-1234",
    status: "failed",
  },
  {
    id: "2",
    title: "Checking Salesforce connection issues",
    timestamp: "15m ago",
    environment: "staging",
    contextEntity: "connector",
    contextName: "salesforce-api",
    status: "running",
  },
  {
    id: "3",
    title: "Reviewing slow data sync",
    timestamp: "1h ago",
    environment: "production",
    contextEntity: "workflow",
    contextName: "main-data-sync",
    status: "success",
  },
  {
    id: "4",
    title: "Fixing database connection timeout",
    timestamp: "3h ago",
    environment: "staging",
    contextEntity: "source",
    contextName: "postgres-backup",
    status: "pending",
  },
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

function toRelativeTime(value: string | undefined): string {
  if (!value) return "Just now"
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return "Just now"
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
  if (diffSeconds < 60) return "Just now"
  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function normalizeTaskStatus(input: string | undefined): Task["status"] {
  const value = (input ?? "").toLowerCase()
  if (value === "failed" || value === "error") return "failed"
  if (value === "running" || value === "executing" || value === "planning") return "running"
  if (value === "pending" || value === "awaiting_approval" || value === "idle") return "pending"
  if (value === "completed" || value === "success" || value === "active" || value === "review") return "success"
  return "pending"
}

function normalizeTask(input: OperatorSessionPayload): Task | null {
  const id = input.id ? String(input.id) : null
  if (!id) return null

  const entityType = String(input.context_entity_type ?? input.contextEntityType ?? "workflow")
  const contextEntity: Task["contextEntity"] =
    entityType === "run" || entityType === "connector" || entityType === "source" ? entityType : "workflow"
  const environmentValue = String(input.environment ?? "staging").toLowerCase()
  const environment: Task["environment"] = environmentValue === "production" ? "production" : "staging"

  return {
    id,
    title: String(input.title ?? "Operator Session"),
    timestamp: toRelativeTime(String(input.created_at ?? input.createdAt ?? "")),
    environment,
    contextEntity,
    contextName: String(input.context_entity_id ?? input.contextEntityId ?? "operator"),
    status: normalizeTaskStatus(input.status),
  }
}

function normalizeTasksResponse(input: OperatorSessionsResponse | undefined): Task[] {
  if (!input) return []

  const sessions = Array.isArray(input.sessions) ? input.sessions : []
  const normalized = sessions
    .map((item) => normalizeTask(item))
    .filter((item): item is Task => item !== null)
  if (normalized.length > 0) return normalized

  const activities = Array.isArray(input.activities) ? input.activities : []
  return activities
    .map((item) => normalizeTask(item))
    .filter((item): item is Task => item !== null)
}



export default function OperatorPage() {
  const { user } = useAuth()
  const [activeTask, setActiveTask] = useState(fallbackTasks[0]?.id ?? "")
  const [activeContext, setActiveContext] = useState("run-1234")
  const [taskInput, setTaskInput] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [executingAction, setExecutingAction] = useState<string | null>(null)
  const [currentFlowStep, setCurrentFlowStep] = useState<string>("task")
  const [selectedModel, setSelectedModel] = useState("auto")
  const [showNewTaskDialog, setShowNewTaskDialog] = useState(false)
  const [newTaskTitle, setNewTaskTitle] = useState("")
  const [isCreatingTask, setIsCreatingTask] = useState(false)
  const [showTaskDetails, setShowTaskDetails] = useState(false)
  const [selectedTaskForDetails, setSelectedTaskForDetails] = useState<Task | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [taskToDelete, setTaskToDelete] = useState<Task | null>(null)
  const [localTasks, setLocalTasks] = useState<Task[]>(fallbackTasks)
  const [generatedPlan, setGeneratedPlan] = useState<{
    findings: typeof fallbackInsightSections
    steps: ActionPlanStep[]
    suggestedActions: SuggestedActionData[]
  } | null>(null)
  const [pendingTaskText, setPendingTaskText] = useState<string>("")

  // Async job hook for durable job queue
  const {
    job: asyncJob,
    isWorking: isAsyncWorking,
    error: asyncError,
    submitJob,
    cancelJob,
    retryJob,
    reset: resetAsyncJob,
  } = useAsyncJob({
    onCompleted: useCallback((job: AgentJob) => {
      if (job.result) {
        const result = job.result
        // Transform async job result into the existing plan format
        setGeneratedPlan({
          findings: [
            {
              id: "summary",
              type: "summary" as const,
              title: "Analysis Summary",
              content: result.analysis_summary || "Analysis complete.",
            },
            {
              id: "finding",
              type: "root-cause" as const,
              title: "Finding",
              content: result.finding_description || "No specific findings.",
            },
          ],
          steps: [
            {
              step: 1,
              title: "Analyze context",
              description: "Review task and gather information",
              status: "completed" as const,
            },
            {
              step: 2,
              title: result.action_title || "Suggested Action",
              description: result.action_description || "Execute recommended action",
              status: "current" as const,
            },
          ],
          suggestedActions: [
            {
              id: `action-${job.jobId}`,
              title: result.action_title || "Execute Recommended Action",
              description: result.action_description || "Apply the suggested fix",
              icon: "RefreshCw",
              environment: "production",
              trustBadges: {
                confidenceScore: Math.round((result.confidence || 0.75) * 100),
                guardrailStatus: result.requires_approval ? "warn" as const : "pass" as const,
                tokenCount: 0,
                approvalRequired: result.requires_approval || false,
              },
            },
          ],
        })
        setCurrentFlowStep("plan")
        setPendingTaskText("")
        toast.success("Analysis complete", {
          description: `Model: ${result.model || "auto"} via ${result.provider || "Gravitre"}`,
        })
      }
    }, []),
    onFailed: useCallback((job: AgentJob) => {
      toast.error("Job failed", {
        description: job.error || "An error occurred during processing",
      })
    }, []),
    onCancelled: useCallback(() => {
      toast.info("Job cancelled")
    }, []),
  })

  // Fetch tasks (formerly sessions)
  const { data: tasksData } = useSWR<OperatorSessionsResponse>(
    "/api/operators/sessions",
    apiFetcher,
    { revalidateOnFocus: false }
  )

  useEffect(() => {
    const normalized = normalizeTasksResponse(tasksData)
    const timer = setTimeout(() => {
      if (normalized.length > 0) {
        setLocalTasks(normalized)
        return
      }
      setLocalTasks(fallbackTasks)
    }, 0)
    return () => clearTimeout(timer)
  }, [tasksData])

  const tasks = localTasks
  useEffect(() => {
    if (!tasks.length) return
    if (!tasks.some((task) => task.id === activeTask)) {
      const timer = setTimeout(() => setActiveTask(tasks[0].id), 0)
      return () => clearTimeout(timer)
    }
  }, [tasks, activeTask])
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

  // Combined working state (sync or async)
  const isProcessing = isGenerating || isAsyncWorking

  const handleGeneratePlan = async () => {
    if (!canCreateTask) return
    
    // Store the task text for display during async processing
    setPendingTaskText(taskInput)
    setTaskInput("")
    setCurrentFlowStep("analysis")

    // Use async job queue
    try {
      await submitJob(
        taskInput,
        activeTask,
        { entityType: activeContext.split("-")[0], entityId: activeContext }
      )
    } catch {
      // Error is handled by the hook and displayed via toast
      setCurrentFlowStep("task")
      setPendingTaskText("")
    }
  }

  const handleCancelJob = async () => {
    try {
      await cancelJob()
      setCurrentFlowStep("task")
      setPendingTaskText("")
    } catch {
      // Error toast is shown by the hook
    }
  }

  const handleRetryJob = async () => {
    try {
      await retryJob()
      setCurrentFlowStep("analysis")
    } catch {
      // Error toast is shown by the hook
    }
  }

  // Legacy sync flow (kept for fallback/feature flag if needed)
  const handleGeneratePlanSync = async () => {
    if (!canCreateTask) return
    setIsGenerating(true)
    setCurrentFlowStep("analysis")

    try {
      const response = await apiFetch(`/api/operators/sessions/${activeTask}/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task: taskInput,
          context: { entityType: activeContext.split("-")[0], entityId: activeContext },
        }),
      })

      if (response.ok) {
        const data = await response.json()
        // Surface AI degradation instead of silently showing a canned plan.
        if (data.aiStatus === "degraded") {
          toast.warning("AI is temporarily degraded", {
            description: "Showing a basic plan. Try regenerating in a moment.",
          })
        }
        if (data.plan) {
          setGeneratedPlan({
            findings: data.plan.reasoning ?? fallbackInsightSections,
            steps: data.plan.steps ?? fallbackActionPlanSteps,
            suggestedActions: data.plan.proposals ?? fallbackSuggestedActions,
          })
          setCurrentFlowStep("plan")
        } else {
          setGeneratedPlan({
            findings: fallbackInsightSections,
            steps: fallbackActionPlanSteps,
            suggestedActions: fallbackSuggestedActions,
          })
          setCurrentFlowStep("plan")
        }
      } else {
        toast.error("Couldn't generate a plan", {
          description: "The operator service returned an error. Please try again.",
        })
        setGeneratedPlan({
          findings: fallbackInsightSections,
          steps: fallbackActionPlanSteps,
          suggestedActions: fallbackSuggestedActions,
        })
        setCurrentFlowStep("plan")
      }
    } catch {
      toast.error("Couldn't reach the operator service", {
        description: "Check your connection and try again.",
      })
      setCurrentFlowStep("plan")
    } finally {
      setIsGenerating(false)
      setTaskInput("")
    }
  }

  const handleOpenNewTaskDialog = () => {
    setNewTaskTitle("")
    setShowNewTaskDialog(true)
  }

  const handleViewTaskDetails = (task: Task) => {
    setSelectedTaskForDetails(task)
    setShowTaskDetails(true)
  }

  const handleRetryTask = (task: Task) => {
    // Update task status to running
    setLocalTasks(prev => prev.map(t => 
      t.id === task.id ? { ...t, status: "running" as const, timestamp: "Just now" } : t
    ))
    toast.success("Task retry initiated", {
      description: `Retrying: ${task.title}`
    })
    // Simulate completion after delay
    setTimeout(() => {
      setLocalTasks(prev => prev.map(t => 
        t.id === task.id ? { ...t, status: "success" as const } : t
      ))
      toast.success("Task completed successfully")
    }, 3000)
  }

  const handleDeleteTask = (task: Task) => {
    setTaskToDelete(task)
    setShowDeleteConfirm(true)
  }

  const confirmDeleteTask = () => {
    if (taskToDelete) {
      setLocalTasks(prev => prev.filter(t => t.id !== taskToDelete.id))
      if (activeTask === taskToDelete.id) {
        setActiveTask(localTasks[0]?.id || "")
      }
      toast.success("Task deleted", {
        description: `"${taskToDelete.title}" has been removed`
      })
      setShowDeleteConfirm(false)
      setTaskToDelete(null)
    }
  }

  const handleCreateTask = async () => {
    if (!newTaskTitle.trim()) {
      toast.error("Please enter a task title")
      return
    }
    
    setIsCreatingTask(true)
    try {
      const response = await apiFetch("/api/operators/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTaskTitle.trim() }),
      })
      if (response.ok) {
        const data = await response.json()
        const normalizedSession = normalizeTask(data.session ?? data)
        if (normalizedSession) {
          setLocalTasks((prev) => [normalizedSession, ...prev])
          setActiveTask(normalizedSession.id)
          setCurrentFlowStep("task")
          setGeneratedPlan(null)
          toast.success("Task created successfully")
          return
        }
      }
      // Create task locally for immediate feedback when API payload is incomplete
      const newTask: Task = {
        id: `${Date.now()}`,
        title: newTaskTitle.trim(),
        timestamp: "Just now",
        environment: "staging",
        contextEntity: "workflow",
        contextName: "new-task",
        status: "pending",
      }
      setLocalTasks((prev) => [newTask, ...prev])
      setActiveTask(newTask.id)
      setCurrentFlowStep("task")
      setGeneratedPlan(null)
      toast.success("Task created successfully")
    } catch {
      // Create task locally even on error
      const newTask: Task = {
        id: `${Date.now()}`,
        title: newTaskTitle.trim(),
        timestamp: "Just now",
        environment: "staging",
        contextEntity: "workflow",
        contextName: "new-task",
        status: "pending",
      }
      setLocalTasks((prev) => [newTask, ...prev])
      setActiveTask(newTask.id)
      setCurrentFlowStep("task")
      setGeneratedPlan(null)
      toast.success("Task created")
    } finally {
      setIsCreatingTask(false)
      setShowNewTaskDialog(false)
      setNewTaskTitle("")
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
          <div className="shrink-0 border-b border-border px-4 md:px-6 py-4 md:py-5 bg-card/50 backdrop-blur-sm relative z-20">
            <div className="flex flex-col gap-4">
              {/* Top row: AI presence and user info */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 md:gap-4">
                  <AIPresence 
                    isProcessing={isProcessing} 
                    isListening={Boolean(taskInput.trim())}
                  />
                  <span className="text-xs text-muted-foreground hidden sm:inline">
                    {user?.email ? `Signed in as ${user.email}` : "Signed in"}
                  </span>
                </div>
                {/* New Task button - visible on all sizes */}
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="h-8 gap-2"
                  onClick={handleOpenNewTaskDialog}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">New Task</span>
                </Button>
              </div>
              
              {/* Bottom row: Controls - scrollable on mobile */}
              <div className="flex items-center gap-2 md:gap-3 overflow-x-auto pb-1 scrollbar-hidden">
                {/* Model Selector - Premium, minimal */}
                <div className="relative flex-shrink-0">
                  <ModelSelector
                    value={selectedModel}
                    onChange={setSelectedModel}
                    inheritedFrom="workspace"
                    onResetToDefault={() => setSelectedModel("auto")}
                    showAdvanced
                    size="sm"
                  />
                </div>
                <div className="h-4 w-px bg-border flex-shrink-0 hidden sm:block" />
                <div className="flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex-shrink-0">
                  <StatusBeacon status="active" size="sm" />
                  <span className="text-xs font-medium text-emerald-500 whitespace-nowrap">12 systems</span>
                </div>
                <div className="flex items-center gap-2 px-2 md:px-3 py-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 flex-shrink-0">
                  <Activity className="h-3.5 w-3.5 text-blue-500" />
                  <span className="text-xs font-medium text-blue-500 whitespace-nowrap">{tasks.length} active</span>
                </div>
              </div>
            </div>
          </div>

          {/* Two Column Layout - Tasks + AI Workspace */}
          <div className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
            {/* Left: Task List (hidden on mobile, shown on desktop) */}
            <div className="hidden md:flex w-56 lg:w-72 shrink-0 border-r border-border bg-card/30 flex-col overflow-hidden">
              <div className="p-3 lg:p-4 border-b border-border shrink-0">
                <h2 className="text-sm font-semibold text-foreground mb-1">Tasks</h2>
                <p className="text-xs text-muted-foreground">Select a task to analyze</p>
              </div>
              <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 lg:p-3 scrollbar-on-hover">
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
                      onView={() => handleViewTaskDetails(task)}
                      onRetry={() => handleRetryTask(task)}
                      onDelete={() => handleDeleteTask(task)}
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
            <div className="flex-1 overflow-y-auto scrollbar-on-hover min-h-0 relative z-0">
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
                      isProcessing={isProcessing}
                      disabled={!activeTask || !activeContext || isProcessing}
                      contextLabel={activeContextLabel || undefined}
                    />
                  </div>
                </div>
              </motion.section>

              {/* 2. ASYNC JOB WORKING STATE */}
              <AnimatePresence mode="wait">
                {isAsyncWorking && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    role="status"
                    aria-live="polite"
                    aria-label="Processing task"
                  >
                    <div className="relative rounded-2xl border border-border bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm overflow-hidden shadow-xl shadow-black/5 p-6">
                      <ParticleField count={40} color="violet" className="opacity-40" />
                      
                      {/* Working state header */}
                      <div className="relative flex items-start gap-4">
                        <div className="flex-shrink-0 h-10 w-10 rounded-full bg-violet-500/20 flex items-center justify-center">
                          <Loader2 className="h-5 w-5 text-violet-500 animate-spin" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-foreground">Working on your task...</h3>
                          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                            {pendingTaskText || "Processing..."}
                          </p>
                          {asyncJob && (
                            <div className="flex items-center gap-3 mt-3">
                              <span className={cn(
                                "text-xs font-medium px-2 py-0.5 rounded-full",
                                asyncJob.status === "queued" && "bg-amber-500/20 text-amber-500",
                                asyncJob.status === "running" && "bg-blue-500/20 text-blue-500",
                              )}>
                                {asyncJob.status === "queued" ? "Queued" : "Running"}
                              </span>
                              {asyncJob.attempts > 1 && (
                                <span className="text-xs text-muted-foreground">
                                  Attempt {asyncJob.attempts}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        
                        {/* Cancel button */}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleCancelJob}
                          className="flex-shrink-0 text-muted-foreground hover:text-destructive"
                        >
                          <X className="h-4 w-4 mr-1" />
                          Cancel
                        </Button>
                      </div>
                      
                      {/* Progress indicator */}
                      <div className="mt-4 h-1 bg-secondary rounded-full overflow-hidden">
                        <motion.div
                          className="h-full bg-gradient-to-r from-violet-500 to-blue-500"
                          initial={{ width: "0%" }}
                          animate={{ width: "100%" }}
                          transition={{ duration: 60, ease: "linear" }}
                        />
                      </div>
                    </div>
                  </motion.section>
                )}
              </AnimatePresence>

              {/* 2b. ASYNC JOB FAILED/CANCELLED STATE */}
              <AnimatePresence mode="wait">
                {asyncJob && (asyncJob.status === "failed" || asyncJob.status === "cancelled") && !isAsyncWorking && (
                  <motion.section 
                    className="mb-10"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    role="alert"
                    aria-live="assertive"
                  >
                    <div className={cn(
                      "relative rounded-2xl border bg-gradient-to-br backdrop-blur-sm overflow-hidden shadow-xl shadow-black/5 p-6",
                      asyncJob.status === "failed" 
                        ? "border-destructive/50 from-destructive/10 to-card/40" 
                        : "border-amber-500/50 from-amber-500/10 to-card/40"
                    )}>
                      <div className="flex items-start gap-4">
                        <div className={cn(
                          "flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center",
                          asyncJob.status === "failed" ? "bg-destructive/20" : "bg-amber-500/20"
                        )}>
                          <AlertCircle className={cn(
                            "h-5 w-5",
                            asyncJob.status === "failed" ? "text-destructive" : "text-amber-500"
                          )} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-foreground">
                            {asyncJob.status === "failed" ? "Task failed" : "Task cancelled"}
                          </h3>
                          {asyncJob.error && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {asyncJob.error}
                            </p>
                          )}
                          {pendingTaskText && (
                            <p className="text-xs text-muted-foreground mt-2 line-clamp-1">
                              Task: {pendingTaskText}
                            </p>
                          )}
                        </div>
                        
                        {/* Retry button */}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRetryJob}
                          className="flex-shrink-0"
                        >
                          <RotateCcw className="h-4 w-4 mr-1" />
                          Retry
                        </Button>
                      </div>
                    </div>
                  </motion.section>
                )}
              </AnimatePresence>

              {/* 2c. LEGACY SYNC PROCESSING STATE (fallback) */}
              <AnimatePresence mode="wait">
                {isGenerating && !isAsyncWorking && (
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
                {!isProcessing && !asyncError && !(asyncJob && (asyncJob.status === "failed" || asyncJob.status === "cancelled")) && (
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
                      isGenerating={isProcessing}
                    />
                  </motion.section>
                )}
              </AnimatePresence>

              {/* 4. SUGGESTED ACTIONS (SECONDARY) */}
              <AnimatePresence>
                {!isProcessing && !asyncError && !(asyncJob && (asyncJob.status === "failed" || asyncJob.status === "cancelled")) && (
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
                {!isProcessing && !asyncError && !(asyncJob && (asyncJob.status === "failed" || asyncJob.status === "cancelled")) && (
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

      {/* New Task Dialog */}
      <Dialog open={showNewTaskDialog} onOpenChange={setShowNewTaskDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create New Task</DialogTitle>
            <DialogDescription>
              Start a new AI-assisted investigation or task.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="task-title">Task Title</Label>
              <Input
                id="task-title"
                placeholder="e.g., Investigate pipeline failure..."
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isCreatingTask) {
                    handleCreateTask()
                  }
                }}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label className="text-muted-foreground">Suggested Tasks</Label>
              <div className="grid gap-2">
                {[
                  "Investigate failed automation run",
                  "Analyze slow data sync",
                  "Review connector errors",
                  "Check system health"
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setNewTaskTitle(suggestion)}
                    className="text-left px-3 py-2 rounded-lg border border-border bg-secondary/50 hover:bg-secondary text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowNewTaskDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateTask}
              disabled={!newTaskTitle.trim() || isCreatingTask}
              className="gap-2"
            >
              {isCreatingTask ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {isCreatingTask ? "Creating..." : "Create Task"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Task Details Dialog */}
      <Dialog open={showTaskDetails} onOpenChange={setShowTaskDetails}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-blue-400" />
              Task Details
            </DialogTitle>
            <DialogDescription>
              View detailed information about this task.
            </DialogDescription>
          </DialogHeader>
          {selectedTaskForDetails && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-muted-foreground text-xs">Title</Label>
                <p className="text-sm font-medium">{selectedTaskForDetails.title}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">Status</Label>
                  <div className={cn(
                    "inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium",
                    selectedTaskForDetails.status === "success" && "bg-emerald-500/10 text-emerald-400",
                    selectedTaskForDetails.status === "failed" && "bg-red-500/10 text-red-400",
                    selectedTaskForDetails.status === "running" && "bg-blue-500/10 text-blue-400",
                    selectedTaskForDetails.status === "pending" && "bg-amber-500/10 text-amber-400"
                  )}>
                    <div className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      selectedTaskForDetails.status === "success" && "bg-emerald-400",
                      selectedTaskForDetails.status === "failed" && "bg-red-400",
                      selectedTaskForDetails.status === "running" && "bg-blue-400",
                      selectedTaskForDetails.status === "pending" && "bg-amber-400"
                    )} />
                    {selectedTaskForDetails.status === "success" ? "Completed" : 
                     selectedTaskForDetails.status === "failed" ? "Failed" :
                     selectedTaskForDetails.status === "running" ? "Running" : "Pending"}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">Environment</Label>
                  <EnvironmentBadge environment={selectedTaskForDetails.environment} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">Created</Label>
                  <p className="text-sm text-muted-foreground">{selectedTaskForDetails.timestamp}</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground text-xs">Context</Label>
                  <p className="text-sm text-muted-foreground">{selectedTaskForDetails.contextName}</p>
                </div>
              </div>
              <div className="pt-4 border-t border-border">
                <Label className="text-muted-foreground text-xs mb-2 block">Actions</Label>
                <div className="flex gap-2">
                  {selectedTaskForDetails.status === "failed" && (
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="gap-1.5"
                      onClick={() => {
                        handleRetryTask(selectedTaskForDetails)
                        setShowTaskDetails(false)
                      }}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      Retry Task
                    </Button>
                  )}
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="gap-1.5 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    onClick={() => {
                      setShowTaskDetails(false)
                      handleDeleteTask(selectedTaskForDetails)
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <Button onClick={() => setShowTaskDetails(false)}>Close</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-400">
              <Trash2 className="h-5 w-5" />
              Delete Task
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this task? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {taskToDelete && (
            <div className="py-4">
              <div className="p-3 rounded-lg bg-secondary/50 border border-border">
                <p className="text-sm font-medium">{taskToDelete.title}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {taskToDelete.contextName} - {taskToDelete.timestamp}
                </p>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={confirmDeleteTask}
              className="gap-1.5"
            >
              <Trash2 className="h-4 w-4" />
              Delete Task
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
