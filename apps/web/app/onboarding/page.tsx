"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { DotLottieAnimation } from "@/components/gravitre/lottie-animation"
import { onboardingApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import {
  ArrowRight,
  ArrowLeft,
  Check,
  Building2,
  Users,
  Sparkles,
  Workflow,
  Plug,
  Bot,
  Play,
  Rocket,
  BarChart3,
  FileText,
  ShoppingCart,
  Headphones,
  Database,
  MessageSquare,
  TrendingUp,
  Shield,
  Zap,
  ChevronRight,
  Loader2,
} from "lucide-react"

// Onboarding steps
const STEPS = [
  { id: "welcome", label: "Welcome" },
  { id: "role", label: "Your Role" },
  { id: "ready", label: "Ready" },
  { id: "path", label: "First Step" },
  { id: "connect", label: "Connect" },
  { id: "operator", label: "Operator" },
  { id: "task", label: "First Task" },
  { id: "success", label: "Success" },
  { id: "next", label: "Next Steps" },
]

const roles = [
  { id: "ops", label: "Operations", description: "Automate business processes", icon: Workflow },
  { id: "sales", label: "Sales & Revenue", description: "Accelerate pipeline", icon: TrendingUp },
  { id: "marketing", label: "Marketing", description: "Scale campaigns", icon: BarChart3 },
  { id: "support", label: "Customer Success", description: "Improve response times", icon: Headphones },
  { id: "data", label: "Data & Analytics", description: "Unify data sources", icon: Database },
  { id: "engineering", label: "Engineering", description: "Automate workflows", icon: Zap },
]

const useCases = [
  { id: "sync", label: "Sync data between systems" },
  { id: "reports", label: "Generate automated reports" },
  { id: "alerts", label: "Set up smart alerts" },
  { id: "workflows", label: "Build approval workflows" },
  { id: "ai", label: "Use AI to process tasks" },
  { id: "other", label: "Something else" },
]

const paths = [
  { 
    id: "operator", 
    title: "Use AI Operator", 
    description: "Tell our AI what you need and watch it work",
    icon: Bot,
    recommended: true,
    time: "2 min"
  },
  { 
    id: "workflow", 
    title: "Build a Workflow", 
    description: "Create an automation step by step",
    icon: Workflow,
    recommended: false,
    time: "5 min"
  },
  { 
    id: "connect", 
    title: "Connect Tools", 
    description: "Start by linking your existing systems",
    icon: Plug,
    recommended: false,
    time: "3 min"
  },
]

const connectors = [
  { id: "salesforce", name: "Salesforce", icon: "SF", color: "bg-blue-500" },
  { id: "hubspot", name: "HubSpot", icon: "HS", color: "bg-orange-500" },
  { id: "slack", name: "Slack", icon: "SL", color: "bg-purple-500" },
  { id: "notion", name: "Notion", icon: "NO", color: "bg-neutral-700" },
  { id: "sheets", name: "Google Sheets", icon: "GS", color: "bg-emerald-500" },
  { id: "postgres", name: "PostgreSQL", icon: "PG", color: "bg-blue-600" },
]

const starterOperators = [
  { 
    id: "sync", 
    name: "Data Sync Assistant", 
    description: "Keeps your systems in sync automatically",
    icon: Database,
    color: "bg-blue-500"
  },
  { 
    id: "report", 
    name: "Report Generator", 
    description: "Creates weekly summaries from your data",
    icon: FileText,
    color: "bg-emerald-500"
  },
  { 
    id: "alert", 
    name: "Smart Alerter", 
    description: "Notifies you when important things happen",
    icon: MessageSquare,
    color: "bg-amber-500"
  },
]

const suggestedNextSteps = [
  { id: "invite", title: "Invite your team", description: "Collaborate with teammates", icon: Users },
  { id: "connect", title: "Connect more tools", description: "Add Slack, HubSpot, and more", icon: Plug },
  { id: "workflow", title: "Build a workflow", description: "Create custom automations", icon: Workflow },
  { id: "explore", title: "Explore AI Operator", description: "Try more complex tasks", icon: Sparkles },
]

export default function OnboardingPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [currentStep, setCurrentStep] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Form state
  const [orgName, setOrgName] = useState("")
  const [selectedRole, setSelectedRole] = useState<string | null>(null)
  const [selectedUseCases, setSelectedUseCases] = useState<string[]>([])
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null)
  const [selectedOperator, setSelectedOperator] = useState<string | null>(null)
  const [taskInput, setTaskInput] = useState("")
  const [taskRunning, setTaskRunning] = useState(false)
  const [taskComplete, setTaskComplete] = useState(false)

  const { data: progress, isLoading: progressLoading, mutate: mutateProgress } = useSWR(
    user ? "onboarding:progress" : null,
    () => onboardingApi.getProgress()
  )

  const stepId = STEPS[currentStep].id

  useEffect(() => {
    if (!progress) return
    const safeIndex = Math.max(0, Math.min(progress.current_step, STEPS.length - 1))
    setCurrentStep(safeIndex)
  }, [progress])

  const handleNext = async () => {
    if (currentStep >= STEPS.length - 1 || isSubmitting) return
    const stepKey = STEPS[currentStep].id
    const stepData: Record<string, unknown> = {
      welcome: { org_name: orgName },
      role: { selected_role: selectedRole, use_cases: selectedUseCases },
      path: { selected_path: selectedPath },
      connect: { selected_connector: selectedConnector },
      operator: { selected_operator: selectedOperator },
      task: { task_input: taskInput, task_complete: taskComplete },
    }[stepKey] ?? {}

    try {
      setIsSubmitting(true)
      const updated = await onboardingApi.completeStep(stepKey, stepData)
      const nextStep = Math.max(currentStep + 1, updated.current_step)
      setCurrentStep(Math.min(nextStep, STEPS.length - 1))
      await mutateProgress(updated, { revalidate: false })
    } catch (error) {
      console.error("Failed to update onboarding step", error)
      toast.error(error instanceof Error ? error.message : "Failed to save onboarding progress")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSkip = async () => {
    if (isSubmitting) return
    try {
      setIsSubmitting(true)
      await onboardingApi.skip()
      router.push("/operator")
    } catch (error) {
      console.error("Failed to skip onboarding", error)
      toast.error(error instanceof Error ? error.message : "Failed to skip onboarding")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleFinish = async () => {
    if (isSubmitting) return
    try {
      setIsSubmitting(true)
      await onboardingApi.completeStep("next", {})
      router.push("/operator")
    } catch (error) {
      console.error("Failed to finish onboarding", error)
      toast.error(error instanceof Error ? error.message : "Failed to finish onboarding")
    } finally {
      setIsSubmitting(false)
    }
  }

  const toggleUseCase = (id: string) => {
    setSelectedUseCases(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const runFirstTask = async () => {
    setTaskRunning(true)
    // Simulate task execution
    await new Promise(resolve => setTimeout(resolve, 3000))
    setTaskRunning(false)
    setTaskComplete(true)
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">Sign in required</p>
          <p className="text-xs text-muted-foreground mt-1">Sign in to continue onboarding.</p>
        </div>
      </div>
    )
  }

  const canProceed = () => {
    switch (stepId) {
      case "welcome": return orgName.trim().length > 0
      case "role": return selectedRole !== null
      case "ready": return true
      case "path": return selectedPath !== null
      case "connect": return true // Can skip
      case "operator": return selectedOperator !== null
      case "task": return taskComplete
      case "success": return true
      case "next": return true
      default: return true
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {progressLoading && (
        <div className="fixed right-4 top-4 z-50 rounded-md border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
          Loading onboarding...
        </div>
      )}
      {/* Progress Bar */}
      <div className="fixed left-0 right-0 top-0 z-50 h-1 bg-secondary">
        <div 
          className="h-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${((currentStep + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      {/* Header */}
      <header className="flex h-16 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-3">
          <img src="/images/gravitre-logo.png" alt="Gravitre" className="h-10 w-auto dark:hidden" />
          <img src="/images/gravitre-icon-white.png" alt="Gravitre" className="h-10 w-auto hidden dark:block" />
        </div>
        <div className="flex items-center gap-2">
          {STEPS.map((step, i) => (
            <div
              key={step.id}
              className={cn(
                "h-2 w-2 rounded-full transition-colors",
                i < currentStep ? "bg-emerald-500" : i === currentStep ? "bg-foreground" : "bg-secondary"
              )}
            />
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={handleSkip} className="text-muted-foreground">
          Skip setup
        </Button>
      </header>

      {/* Main Content */}
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-2xl">

          {/* Step 1: Welcome */}
          {stepId === "welcome" && (
            <div className="space-y-8 text-center">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/10">
                <Sparkles className="h-10 w-10 text-emerald-500" />
              </div>
              <div className="space-y-3">
                <h1 className="text-4xl font-semibold tracking-tight text-foreground">
                  Welcome to Gravitre
                </h1>
                <p className="text-lg text-muted-foreground">
                  Let&apos;s set up your AI-powered workspace in under 2 minutes.
                </p>
              </div>
              <div className="mx-auto max-w-sm space-y-3">
                <label className="block text-left text-sm font-medium text-foreground">
                  What&apos;s your organization called?
                </label>
                <input
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Acme Corp"
                  className="w-full rounded-lg border border-border bg-secondary px-4 py-3 text-foreground placeholder:text-muted-foreground focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  autoFocus
                />
              </div>
            </div>
          )}

          {/* Step 2: Role Selection */}
          {stepId === "role" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  What&apos;s your primary focus?
                </h1>
                <p className="text-muted-foreground">
                  This helps us personalize your experience
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {roles.map((role) => (
                  <button
                    key={role.id}
                    onClick={() => setSelectedRole(role.id)}
                    className={cn(
                      "flex items-center gap-4 rounded-lg border p-4 text-left transition-all",
                      selectedRole === role.id
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-border bg-card hover:border-foreground/20"
                    )}
                  >
                    <div className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-lg",
                      selectedRole === role.id ? "bg-emerald-500" : "bg-secondary"
                    )}>
                      <role.icon className={cn(
                        "h-5 w-5",
                        selectedRole === role.id ? "text-white" : "text-muted-foreground"
                      )} />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{role.label}</p>
                      <p className="text-sm text-muted-foreground">{role.description}</p>
                    </div>
                  </button>
                ))}
              </div>
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">What do you want to accomplish? (Select all that apply)</p>
                <div className="flex flex-wrap gap-2">
                  {useCases.map((uc) => (
                    <button
                      key={uc.id}
                      onClick={() => toggleUseCase(uc.id)}
                      className={cn(
                        "rounded-full border px-4 py-2 text-sm transition-all",
                        selectedUseCases.includes(uc.id)
                          ? "border-emerald-500 bg-emerald-500/10 text-foreground"
                          : "border-border text-muted-foreground hover:border-foreground/20"
                      )}
                    >
                      {uc.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Workspace Ready */}
          {stepId === "ready" && (
            <div className="space-y-8 text-center">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500">
                <Check className="h-10 w-10 text-white" />
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  {orgName}&apos;s workspace is ready
                </h1>
                <p className="text-lg text-muted-foreground">
                  Now let&apos;s get you to your first AI-powered result.
                </p>
              </div>
              <div className="mx-auto max-w-md rounded-lg border border-border bg-card p-6">
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary">
                    <Building2 className="h-6 w-6 text-foreground" />
                  </div>
                  <div className="text-left">
                    <p className="font-medium text-foreground">{orgName}</p>
                    <p className="text-sm text-muted-foreground">Production workspace</p>
                  </div>
                  <div className="ml-auto">
                    <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-500">
                      Active
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Choose Path */}
          {stepId === "path" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  How would you like to start?
                </h1>
                <p className="text-muted-foreground">
                  Choose the fastest path to your first result
                </p>
              </div>
              <div className="space-y-3">
                {paths.map((path) => (
                  <button
                    key={path.id}
                    onClick={() => setSelectedPath(path.id)}
                    className={cn(
                      "flex w-full items-center gap-4 rounded-lg border p-5 text-left transition-all",
                      selectedPath === path.id
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-border bg-card hover:border-foreground/20"
                    )}
                  >
                    <div className={cn(
                      "flex h-12 w-12 items-center justify-center rounded-lg",
                      selectedPath === path.id ? "bg-emerald-500" : "bg-secondary"
                    )}>
                      <path.icon className={cn(
                        "h-6 w-6",
                        selectedPath === path.id ? "text-white" : "text-muted-foreground"
                      )} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground">{path.title}</p>
                        {path.recommended && (
                          <span className="rounded-full bg-emerald-500 px-2 py-0.5 text-[10px] font-medium text-white">
                            Recommended
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{path.description}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-muted-foreground">{path.time}</p>
                    </div>
                    <ChevronRight className={cn(
                      "h-5 w-5",
                      selectedPath === path.id ? "text-emerald-500" : "text-muted-foreground"
                    )} />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 5: Connect First System */}
          {stepId === "connect" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  Connect your first tool
                </h1>
                <p className="text-muted-foreground">
                  Optional - you can always add these later
                </p>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {connectors.map((connector) => (
                  <button
                    key={connector.id}
                    onClick={() => setSelectedConnector(
                      selectedConnector === connector.id ? null : connector.id
                    )}
                    className={cn(
                      "flex flex-col items-center gap-3 rounded-lg border p-5 transition-all",
                      selectedConnector === connector.id
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-border bg-card hover:border-foreground/20"
                    )}
                  >
                    <div className={cn("flex h-12 w-12 items-center justify-center rounded-lg text-white font-semibold", connector.color)}>
                      {connector.icon}
                    </div>
                    <p className="text-sm font-medium text-foreground">{connector.name}</p>
                    {selectedConnector === connector.id && (
                      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500">
                        <Check className="h-3 w-3 text-white" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
              <p className="text-center text-sm text-muted-foreground">
                20+ more integrations available in settings
              </p>
            </div>
          )}

          {/* Step 6: Choose Starter Operator */}
          {stepId === "operator" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  Choose your first AI assistant
                </h1>
                <p className="text-muted-foreground">
                  Each operator is pre-configured for specific tasks
                </p>
              </div>
              <div className="space-y-3">
                {starterOperators.map((op) => (
                  <button
                    key={op.id}
                    onClick={() => setSelectedOperator(op.id)}
                    className={cn(
                      "flex w-full items-center gap-4 rounded-lg border p-5 text-left transition-all",
                      selectedOperator === op.id
                        ? "border-emerald-500 bg-emerald-500/10"
                        : "border-border bg-card hover:border-foreground/20"
                    )}
                  >
                    <div className={cn("flex h-14 w-14 items-center justify-center rounded-full", op.color)}>
                      <op.icon className="h-7 w-7 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground">{op.name}</p>
                      <p className="text-sm text-muted-foreground">{op.description}</p>
                    </div>
                    {selectedOperator === op.id && (
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500">
                        <Check className="h-4 w-4 text-white" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Step 7: Run First Task */}
          {stepId === "task" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  Let&apos;s run your first task
                </h1>
                <p className="text-muted-foreground">
                  Tell your AI assistant what to do
                </p>
              </div>
              
              {!taskComplete ? (
                <div className="space-y-6">
                  <div className="rounded-lg border border-border bg-card p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500">
                        <Bot className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <p className="font-medium text-foreground">
                          {starterOperators.find(o => o.id === selectedOperator)?.name || "AI Assistant"}
                        </p>
                        <p className="text-xs text-muted-foreground">Ready to help</p>
                      </div>
                    </div>
                    <div className="space-y-3">
                      <p className="text-sm text-muted-foreground">Try asking:</p>
                      <div className="flex flex-wrap gap-2">
                        {[
                          "Generate a summary of last week's activity",
                          "Check for any data discrepancies",
                          "Create a status report"
                        ].map((prompt, i) => (
                          <button
                            key={i}
                            onClick={() => setTaskInput(prompt)}
                            className="rounded-full border border-border bg-secondary px-3 py-1.5 text-sm text-foreground hover:bg-secondary/80"
                          >
                            {prompt}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      value={taskInput}
                      onChange={(e) => setTaskInput(e.target.value)}
                      placeholder="Type a task or choose from above..."
                      className="w-full rounded-lg border border-border bg-secondary px-4 py-4 pr-24 text-foreground placeholder:text-muted-foreground focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    />
                    <Button
                      onClick={runFirstTask}
                      disabled={!taskInput.trim() || taskRunning}
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-emerald-500 hover:bg-emerald-600"
                    >
                      {taskRunning ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Run
                        </>
                      )}
                    </Button>
                  </div>
                  {taskRunning && (
                    <div className="rounded-lg border border-border bg-card p-4">
                      <div className="flex items-center gap-3">
                        <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
                        <div>
                          <p className="text-sm font-medium text-foreground">Processing your request...</p>
                          <p className="text-xs text-muted-foreground">This usually takes a few seconds</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 p-6">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500">
                      <Check className="h-5 w-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground">Task completed successfully</p>
                      <p className="mt-1 text-sm text-muted-foreground">{taskInput}</p>
                      <div className="mt-4 rounded-lg border border-border bg-card p-4">
                        <p className="text-sm text-muted-foreground">Result preview:</p>
                        <p className="mt-2 text-sm text-foreground">
                          Generated a comprehensive summary including 12 key metrics, 3 action items, and performance trends. The full report has been saved to your workspace.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 8: Success */}
          {stepId === "success" && (
            <div className="space-y-8 text-center">
              {/* Celebratory Lottie Animation */}
              <DotLottieAnimation
                src="https://lottie.host/f7a01fe3-9450-44d9-8c6e-277ed9c9cb1e/EOWNoqCMxc.lottie"
                className="mx-auto w-40 h-40"
                loop={true}
                autoplay={true}
              />
              <div className="space-y-3">
                <h1 className="text-4xl font-semibold tracking-tight text-foreground">
                  You did it!
                </h1>
                <p className="text-lg text-muted-foreground">
                  You&apos;ve completed your first AI-powered task with Gravitre.
                </p>
              </div>
              <div className="mx-auto max-w-md rounded-lg border border-border bg-card p-6">
                <div className="grid grid-cols-3 gap-6">
                  <div>
                    <p className="text-3xl font-semibold text-emerald-500">1</p>
                    <p className="text-sm text-muted-foreground">Task completed</p>
                  </div>
                  <div>
                    <p className="text-3xl font-semibold text-foreground">3s</p>
                    <p className="text-sm text-muted-foreground">Time saved</p>
                  </div>
                  <div>
                    <p className="text-3xl font-semibold text-foreground">1</p>
                    <p className="text-sm text-muted-foreground">AI agent active</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 9: Suggested Next Steps */}
          {stepId === "next" && (
            <div className="space-y-8">
              <div className="space-y-3 text-center">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                  What&apos;s next?
                </h1>
                <p className="text-muted-foreground">
                  Here are some ways to get more value from Gravitre
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {suggestedNextSteps.map((step) => (
                  <button
                    key={step.id}
                    className="flex items-start gap-4 rounded-lg border border-border bg-card p-5 text-left transition-all hover:border-foreground/20"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                      <step.icon className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium text-foreground">{step.title}</p>
                      <p className="text-sm text-muted-foreground">{step.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Footer Navigation */}
      <footer className="border-t border-border px-6 py-4">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={currentStep === 0}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <p className="text-sm text-muted-foreground">
            Step {currentStep + 1} of {STEPS.length}
          </p>
          {stepId === "next" ? (
            <Button onClick={handleFinish} className="gap-2 bg-emerald-500 hover:bg-emerald-600">
              Go to Dashboard
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              onClick={handleNext}
              disabled={!canProceed() || isSubmitting}
              className="gap-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50"
            >
              Continue
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </footer>
    </div>
  )
}
