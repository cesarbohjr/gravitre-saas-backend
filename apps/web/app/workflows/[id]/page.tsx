"use client"

import { use, useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { EnvironmentBadge } from "@/components/gravitre/environment-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Play,
  Pause,
  ArrowLeft,
  Sparkles,
  Plus,
  Database,
  Bot,
  Zap,
  Shield,
  ChevronRight,
  Lightbulb,
  MessageSquare,
  Clock,
  CheckCircle2,
  Circle,
  MoreHorizontal,
  Settings,
  Trash2,
  Copy,
  ExternalLink,
} from "lucide-react"
import Link from "next/link"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import { toast } from "sonner"

interface WorkflowResponse {
  workflow: Record<string, unknown>
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
  config: Record<string, unknown>
}

interface WorkflowHealthResponse {
  healthScore: number
  dimensions: Record<string, number>
  trendData: Array<{ recordedAt: string; healthScore: number }>
}

interface WorkflowRecommendationsResponse {
  recommendations: Array<{
    id: string
    issue: string
    confidence: number | null
  }>
}

const fallbackAutomationData = {
  id: "wf-001",
  name: "Sync customer data from Salesforce to internal systems",
  description: "Automatically pulls customer records, validates and cleans the data, then syncs to your database",
  status: "active" as const,
  environment: "production" as const,
  version: "v2.4.1",
  lastRun: "2 minutes ago",
  lastRunStatus: "success" as const,
  schedule: "Every 15 minutes",
  successRate: 98.5,
  totalRuns: 12847,
}

// Flow steps with simplified terminology
const fallbackFlowSteps = [
  {
    id: "step-1",
    name: "Pull customer records",
    system: "Salesforce",
    systemType: "data-source",
    environment: "production" as const,
    status: "completed" as const,
    description: "Fetch all customer records updated in the last 24 hours",
    inputs: ["Salesforce API credentials", "Last sync timestamp"],
    outputs: ["Raw customer records (JSON)"],
    requiresApproval: false,
  },
  {
    id: "step-2",
    name: "Validate and clean data",
    system: "Data Validator Agent",
    systemType: "agent",
    environment: "production" as const,
    status: "completed" as const,
    description: "Check for missing fields, duplicates, and format issues",
    inputs: ["Raw customer records"],
    outputs: ["Validated records", "Error report"],
    requiresApproval: false,
  },
  {
    id: "step-3",
    name: "Review data quality",
    system: "Quality Gate",
    systemType: "approval",
    environment: "production" as const,
    status: "pending" as const,
    description: "Human review required before proceeding to production database",
    inputs: ["Validated records", "Quality score"],
    outputs: ["Approved records"],
    requiresApproval: true,
    adminOnly: true,
  },
  {
    id: "step-4",
    name: "Sync to database",
    system: "PostgreSQL",
    systemType: "connected-system",
    environment: "production" as const,
    status: "waiting" as const,
    description: "Write validated records to the main customer database",
    inputs: ["Approved records"],
    outputs: ["Sync confirmation", "Record count"],
    requiresApproval: false,
  },
]

const examplePrompts = [
  "Sync CRM data daily",
  "Alert Slack on failures",
  "Add data validation step",
]

const systemIcons: Record<string, typeof Database> = {
  "data-source": Database,
  "agent": Bot,
  "approval": Shield,
  "connected-system": Zap,
}

const flowPhases = [
  { label: "Build", status: "completed", description: "Design and configure your automation flow" },
  { label: "Review", status: "completed", description: "Validate steps and test in staging" },
  { label: "Activate", status: "current", description: "Deploy to production environment" },
  { label: "Run", status: "upcoming", description: "Monitor live execution and performance" },
]

export default function WorkflowDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const { data: workflowData, error: workflowError, isLoading: isLoadingWorkflow } = useSWR<WorkflowResponse>(
    `/api/workflows/${id}`,
    fetcher
  )
  const { data: healthData } = useSWR<WorkflowHealthResponse>(`/api/workflows/${id}/health`, fetcher)
  const { data: recommendationData } = useSWR<WorkflowRecommendationsResponse>(
    `/api/workflows/${id}/recommendations`,
    fetcher
  )

  const automationData = useMemo(() => {
    const workflow = workflowData?.workflow
    if (!workflow) return fallbackAutomationData
    const healthScore = Math.max(0, Math.min(100, Math.round(Number(healthData?.healthScore ?? 0))))
    return {
      id: String(workflow.id ?? id),
      name: String(workflow.name ?? fallbackAutomationData.name),
      description: String(workflow.description ?? fallbackAutomationData.description),
      status: (String(workflow.status ?? "draft") as "active" | "paused" | "draft"),
      environment: (String(workflow.environment ?? "production") as "production" | "staging"),
      version: `v${String((workflowData?.config?.version as number | undefined) ?? 1)}.0`,
      lastRun: String(workflow.updatedAt ?? "recently"),
      lastRunStatus: "success" as const,
      schedule: String((workflowData?.config?.schedule as string | undefined) ?? "Manual"),
      successRate: healthScore,
      totalRuns: healthData?.trendData?.length ?? 0,
    }
  }, [healthData?.healthScore, healthData?.trendData?.length, id, workflowData?.config?.version, workflowData?.config?.schedule, workflowData?.workflow])

  const flowSteps = useMemo(() => {
    const nodes = workflowData?.nodes
    if (!nodes || nodes.length === 0) return fallbackFlowSteps
    return nodes.map((node, index) => {
      const nodeType = String(node.type ?? "task")
      const mappedType =
        nodeType === "source"
          ? "data-source"
          : nodeType === "agent"
          ? "agent"
          : nodeType === "approval"
          ? "approval"
          : "connected-system"
      return {
        id: String(node.id ?? `step-${index + 1}`),
        name: String(node.name ?? `Step ${index + 1}`),
        system: String(node.type ?? "Workflow node"),
        systemType: mappedType as "data-source" | "agent" | "approval" | "connected-system",
        environment: automationData.environment,
        status: (index === 0 ? "completed" : index === 1 ? "pending" : "waiting") as
          | "completed"
          | "pending"
          | "waiting",
        description: String(node.description ?? "No description available."),
        inputs: Array.isArray(node.inputs) ? (node.inputs as string[]) : ["Input context"],
        outputs: Array.isArray(node.outputs) ? (node.outputs as string[]) : ["Output artifact"],
        requiresApproval: mappedType === "approval",
      }
    })
  }, [automationData.environment, workflowData?.nodes])

  const [selectedStep, setSelectedStep] = useState<string | null>(null)
  const [aiPrompt, setAiPrompt] = useState("")
  const promptSuggestions =
    recommendationData?.recommendations?.slice(0, 3).map((item) => item.issue) ?? examplePrompts

  const selectedStepData = flowSteps.find((s) => s.id === selectedStep)

  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    if (!selectedStep && flowSteps.length > 0) {
      setSelectedStep(flowSteps[0].id)
    }
  }, [flowSteps, selectedStep])

  useEffect(() => {
    if (workflowError) {
      toast.error("Failed to load workflow details")
    }
  }, [workflowError])
  
  const handleGenerateWorkflow = async () => {
    if (aiPrompt.trim()) {
      setIsGenerating(true)
      await new Promise(resolve => setTimeout(resolve, 1500))
      setIsGenerating(false)
      toast.success("Flow prompt captured", {
        description: "Planner integration is queued for this workflow.",
      })
      setAiPrompt("")
    }
  }

  if (isLoadingWorkflow) {
    return (
      <AppShell>
        <div className="p-6 space-y-4">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-80 w-full" />
        </div>
      </AppShell>
    )
  }

  if (workflowError || !workflowData?.workflow) {
    return (
      <AppShell>
        <EmptyState
          variant="error"
          title="Workflow not found"
          description="We could not load this workflow."
        />
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex-1 flex flex-col min-h-0">
        {/* Header - Goal Based */}
        <div className="flex-shrink-0 border-b border-border px-4 md:px-6 py-3 md:py-4">
          <div className="flex items-center gap-2 md:gap-3 mb-3">
            <Link
              href="/workflows"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <span className="hidden sm:inline text-muted-foreground text-sm">Automations</span>
            <ChevronRight className="hidden sm:inline h-3 w-3 text-muted-foreground" />
            <span className="text-sm text-foreground truncate">Customer Sync</span>
          </div>

          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="space-y-2 min-w-0">
              <div className="flex items-center gap-3">
                <h1 className="text-base md:text-lg font-semibold text-foreground truncate">{automationData.name}</h1>
              </div>
              <p className="text-xs md:text-sm text-muted-foreground line-clamp-2">
                {automationData.description}
              </p>
              <div className="flex flex-wrap items-center gap-2 md:gap-3 pt-1">
                <StatusBadge status={automationData.status} />
                <EnvironmentBadge environment={automationData.environment} />
                <span className="hidden sm:inline text-xs text-muted-foreground">
                  Last run: {automationData.lastRun}
                </span>
                <span className="hidden md:inline text-xs text-success flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  {automationData.successRate}% success rate
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button variant="outline" size="sm" className="gap-2">
                <Pause className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Pause</span>
              </Button>
              <Button size="sm" className="gap-2">
                <Play className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Run Now</span>
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem>
                    <Settings className="h-4 w-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Copy className="h-4 w-4 mr-2" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="text-destructive">
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Flow Phase Progress Bar */}
        <div className="flex-shrink-0 border-b border-border px-6 py-4 bg-secondary/20">
          <div className="max-w-2xl mx-auto">
            <div className="relative flex items-center justify-between">
              {/* Progress Line Background */}
              <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-[2px] bg-border" />
              
              {/* Progress Line Filled */}
              <div 
                className="absolute left-0 top-1/2 -translate-y-1/2 h-[2px] bg-gradient-to-r from-emerald-500 via-emerald-500 to-blue-500 transition-all duration-500"
                style={{ 
                  width: `${(flowPhases.findIndex(p => p.status === "current") / (flowPhases.length - 1)) * 100}%` 
                }}
              />

              {flowPhases.map((phase, index) => {
                const isCompleted = phase.status === "completed"
                const isCurrent = phase.status === "current"
                const isUpcoming = phase.status === "upcoming"

                return (
                  <div key={phase.label} className="relative group z-10">
                    {/* Step Circle */}
                    <div className="flex flex-col items-center">
                      <div
                        className={`
                          relative flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all duration-300
                          ${isCompleted 
                            ? "bg-emerald-500 border-emerald-500 text-white" 
                            : isCurrent 
                              ? "bg-blue-500 border-blue-500 text-white shadow-[0_0_12px_rgba(59,130,246,0.5)]" 
                              : "bg-card border-border text-muted-foreground"
                          }
                          ${isCurrent ? "scale-110" : "group-hover:scale-105"}
                        `}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <span className="text-xs font-semibold">{index + 1}</span>
                        )}
                        
                        {/* Glow effect for current */}
                        {isCurrent && (
                          <div className="absolute inset-0 rounded-full bg-blue-500/30 animate-ping" />
                        )}
                      </div>

                      {/* Label */}
                      <span
                        className={`
                          mt-2 text-xs font-medium transition-colors duration-200
                          ${isCurrent 
                            ? "text-foreground" 
                            : isCompleted 
                              ? "text-emerald-400" 
                              : "text-muted-foreground"
                          }
                        `}
                      >
                        {phase.label}
                      </span>
                    </div>

                    {/* Hover Tooltip */}
                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-20">
                      <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-lg whitespace-nowrap">
                        <p className="text-xs font-medium text-foreground">{phase.label}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">{phase.description}</p>
                        <div className="absolute left-1/2 -translate-x-1/2 top-full w-2 h-2 bg-popover border-r border-b border-border rotate-45 -mt-1" />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex min-h-0 flex-col lg:flex-row">
          {/* Left Panel - AI Entry + Flow */}
          <div className="flex-1 lg:border-r border-border overflow-auto">
            <div className="p-4 md:p-6 space-y-4 md:space-y-6">
              {/* AI Entry Point */}
              <Card className="bg-secondary/30 border-border">
                <CardContent className="p-4">
                  <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3 block">
                    What do you want this automation to do?
                  </label>
                  <div className="flex gap-2">
                    <Input
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="Describe a change or addition..."
                      className="flex-1 bg-background border-border"
                    />
                    <Button onClick={handleGenerateWorkflow} className="gap-2" disabled={isGenerating}>
                      <Sparkles className="h-4 w-4" />
                      {isGenerating ? "Updating..." : "Update Flow"}
                    </Button>
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="text-xs text-muted-foreground">Try:</span>
                    {promptSuggestions.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => setAiPrompt(prompt)}
                        className="text-xs text-muted-foreground hover:text-foreground bg-muted hover:bg-muted/80 px-2 py-1 rounded transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Flow Steps */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                    Automation Flow
                  </h2>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-success" />
                      Done
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-warning" />
                      Waiting
                    </span>
                    <span className="flex items-center gap-1">
                      <Circle className="h-3 w-3 text-muted-foreground" />
                      Pending
                    </span>
                  </div>
                </div>

                <div className="space-y-0">
                  {flowSteps.map((step, index) => {
                    const Icon = systemIcons[step.systemType] || Zap
                    const isSelected = selectedStep === step.id
                    const stepNumber = index + 1
                    const isLastStep = index === flowSteps.length - 1

                    return (
                      <div key={step.id} className="relative">
                        {/* Step Card */}
                        <button
                          onClick={() => setSelectedStep(step.id)}
                          className={`w-full text-left rounded-lg border p-4 transition-all ${
                            isSelected
                              ? "border-info bg-info/5 shadow-[0_0_0_1px_hsl(var(--info)/0.3)]"
                              : "border-border bg-card hover:border-muted-foreground/50"
                          }`}
                        >
                          <div className="flex items-start gap-4">
                            {/* Step Number + Icon */}
                            <div className="relative">
                              <div
                                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg ${
                                  step.systemType === "agent"
                                    ? "bg-info/10 text-info"
                                    : step.systemType === "approval"
                                      ? "bg-warning/10 text-warning"
                                      : step.systemType === "data-source"
                                        ? "bg-success/10 text-success"
                                        : "bg-muted text-muted-foreground"
                                }`}
                              >
                                <Icon className="h-5 w-5" />
                              </div>
                              {/* Step number badge */}
                              <div className="absolute -top-1.5 -left-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-secondary border border-border text-[10px] font-semibold text-muted-foreground">
                                {stepNumber}
                              </div>
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-foreground">
                                  {step.name}
                                </span>
                                {step.requiresApproval && (
                                  <span className="flex items-center gap-1 text-[10px] font-medium text-warning bg-warning/10 border border-warning/20 px-1.5 py-0.5 rounded">
                                    <Shield className="h-2.5 w-2.5" />
                                    Approval required
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{step.system}</span>
                                {step.status === "completed" && (
                                  <>
                                    <span className="text-muted-foreground/50">|</span>
                                    <span className="text-success">Completed</span>
                                  </>
                                )}
                                {step.status === "pending" && (
                                  <>
                                    <span className="text-muted-foreground/50">|</span>
                                    <span className="text-warning">Awaiting approval</span>
                                  </>
                                )}
                                {step.status === "waiting" && (
                                  <>
                                    <span className="text-muted-foreground/50">|</span>
                                    <span className="text-muted-foreground">Ready to run</span>
                                  </>
                                )}
                              </div>
                            </div>

                            {/* Status */}
                            <div className="flex items-center gap-2">
                              {step.status === "completed" ? (
                                <CheckCircle2 className="h-5 w-5 text-success" />
                              ) : step.status === "pending" ? (
                                <Clock className="h-5 w-5 text-warning" />
                              ) : (
                                <Circle className="h-5 w-5 text-muted-foreground" />
                              )}
                            </div>
                          </div>
                        </button>

                        {/* Flow Arrow Connector */}
                        {!isLastStep && (
                          <div className="flex justify-center py-1">
                            <div className="flex flex-col items-center">
                              <div className="h-2 w-px bg-gradient-to-b from-border to-muted-foreground/30" />
                              <ChevronRight className="h-3 w-3 text-muted-foreground/50 rotate-90" />
                              <div className="h-2 w-px bg-gradient-to-b from-muted-foreground/30 to-border" />
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {/* Add Step Button */}
                  <button className="w-full flex items-center justify-center gap-2 rounded-lg border border-dashed border-border hover:border-muted-foreground/50 p-4 text-sm text-muted-foreground hover:text-foreground transition-colors">
                    <Plus className="h-4 w-4" />
                    Add step
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel - Step Configuration - hidden on mobile */}
          <div className="hidden lg:block w-96 flex-shrink-0 overflow-auto bg-secondary/20">
            {selectedStepData ? (
              <div className="p-6 space-y-6">
                {/* Step Header */}
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    {(() => {
                      const Icon = systemIcons[selectedStepData.systemType] || Zap
                      return (
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                            selectedStepData.systemType === "agent"
                              ? "bg-info/10 text-info"
                              : selectedStepData.systemType === "approval"
                                ? "bg-warning/10 text-warning"
                                : selectedStepData.systemType === "data-source"
                                  ? "bg-success/10 text-success"
                                  : "bg-muted text-muted-foreground"
                          }`}
                        >
                          <Icon className="h-5 w-5" />
                        </div>
                      )
                    })()}
                    <div>
                      <h3 className="text-sm font-medium text-foreground">
                        {selectedStepData.name}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {selectedStepData.system}
                      </p>
                    </div>
                  </div>
                </div>

                {/* What This Step Does */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    What this step does
                  </h4>
                  <p className="text-sm text-foreground">
                    {selectedStepData.description}
                  </p>
                </div>

                {/* Inputs - with source indication */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Inputs
                  </h4>
                  <ul className="space-y-2">
                    {selectedStepData.inputs.map((input, idx) => {
                      // Find previous step to show data source
                      const stepIndex = flowSteps.findIndex(s => s.id === selectedStepData.id)
                      const prevStep = stepIndex > 0 ? flowSteps[stepIndex - 1] : null
                      
                      return (
                        <li
                          key={input}
                          className="text-sm bg-muted/30 rounded-md p-2 border border-border"
                        >
                          <div className="flex items-center gap-2 text-foreground">
                            <div className="h-1.5 w-1.5 rounded-full bg-info" />
                            {input}
                          </div>
                          {prevStep && idx === 0 && (
                            <div className="text-[10px] text-muted-foreground mt-1 pl-3.5">
                              From: Step {stepIndex}. {prevStep.name}
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </div>

                {/* Outputs - with destination indication */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Outputs
                  </h4>
                  <ul className="space-y-2">
                    {selectedStepData.outputs.map((output, idx) => {
                      // Find next step to show data destination
                      const stepIndex = flowSteps.findIndex(s => s.id === selectedStepData.id)
                      const nextStep = stepIndex < flowSteps.length - 1 ? flowSteps[stepIndex + 1] : null
                      
                      return (
                        <li
                          key={output}
                          className="text-sm bg-success/5 rounded-md p-2 border border-success/20"
                        >
                          <div className="flex items-center gap-2 text-foreground">
                            <div className="h-1.5 w-1.5 rounded-full bg-success" />
                            {output}
                          </div>
                          {nextStep && idx === 0 && (
                            <div className="text-[10px] text-muted-foreground mt-1 pl-3.5">
                              To: Step {stepIndex + 2}. {nextStep.name}
                            </div>
                          )}
                          {!nextStep && (
                            <div className="text-[10px] text-success mt-1 pl-3.5">
                              Final output
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                </div>

                {/* Environment */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Environment
                  </h4>
                  <EnvironmentBadge environment={selectedStepData.environment} />
                </div>

                {/* Safety Rules */}
                {(selectedStepData.requiresApproval || selectedStepData.adminOnly) && (
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Safety Rules
                    </h4>
                    <div className="space-y-2">
                      {selectedStepData.requiresApproval && (
                        <div className="flex items-center gap-2 text-sm text-warning">
                          <Shield className="h-4 w-4" />
                          Needs approval first
                        </div>
                      )}
                      {selectedStepData.adminOnly && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Shield className="h-4 w-4" />
                          Admin only
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* AI Assist */}
                <div className="pt-4 border-t border-border">
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                    AI Assist
                  </h4>
                  <div className="space-y-2">
                    <button className="w-full flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground p-2 rounded hover:bg-muted/50 transition-colors">
                      <Lightbulb className="h-4 w-4" />
                      Improve this step
                    </button>
                    <button className="w-full flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground p-2 rounded hover:bg-muted/50 transition-colors">
                      <MessageSquare className="h-4 w-4" />
                      Explain this step
                    </button>
                    <button className="w-full flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground p-2 rounded hover:bg-muted/50 transition-colors">
                      <Sparkles className="h-4 w-4" />
                      Suggest next step
                    </button>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-4 border-t border-border">
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="flex-1">
                      Configure
                    </Button>
                    <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                Select a step to view details
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 border-t border-border px-6 py-3 bg-secondary/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>
                <Clock className="h-3 w-3 inline mr-1" />
                Runs automatically: {automationData.schedule}
              </span>
              <Link
                href={`/workflows/${automationData.id}/schedules`}
                className="text-info hover:underline flex items-center gap-1"
              >
                Edit schedule
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {automationData.totalRuns.toLocaleString()} total runs
              </span>
              <Link href="/runs">
                <Button variant="outline" size="sm" className="text-xs h-7">
                  View run history
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
