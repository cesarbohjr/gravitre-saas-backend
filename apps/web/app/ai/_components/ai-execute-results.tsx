"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { ArrowRight, CheckCircle, Eye, Loader2, Play } from "lucide-react"
import { MesonInsightsPanel } from "@/components/gravitre/ai-insights-panel"
import { SuggestedActions } from "@/components/gravitre/suggested-actions"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { AgentJob } from "@/hooks/use-async-job"
import {
  DEFAULT_RESULT_BLOCK_ORDER,
  DraggableResultStack,
  type LayoutColumn,
  type ResultBlockId,
} from "./draggable-result-stack"
import { resolveBlockColumn } from "./ai-layout-storage"
import {
  fallbackActionPlanSteps,
  fallbackSuggestedActionsList,
  resolveAnalysisConfidence,
  resolveConfidenceDataPoints,
  type ActionPlanStep,
  type InlineExecutePlan,
} from "@/lib/ai-inline-execute"
import { toast } from "sonner"

function EmptyPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card/40 px-4 py-5 text-sm text-muted-foreground">
      <p className="font-medium text-foreground">{title}</p>
      <p className="mt-1 text-xs">{body}</p>
    </div>
  )
}

function filterSections<T extends { type?: string; id?: string }>(
  sections: T[],
  types: string[],
): T[] {
  return sections.filter((section) => types.includes(String(section.type ?? section.id ?? "")))
}

type AiExecuteResultsProps = {
  plan: InlineExecutePlan | null
  job: AgentJob | null
  isProcessing: boolean
  error: string | null
  blockOrder?: ResultBlockId[]
  enabledBlocks?: ResultBlockId[]
  onReorderBlocks?: (next: ResultBlockId[]) => void
  blockColumns?: Partial<Record<ResultBlockId, LayoutColumn>>
  onMoveBlockToColumn?: (blockId: ResultBlockId, target: LayoutColumn) => void
  column?: LayoutColumn
  compact?: boolean
}

export function AiExecuteResults({
  plan,
  job,
  isProcessing,
  error,
  blockOrder,
  enabledBlocks,
  onReorderBlocks,
  blockColumns,
  onMoveBlockToColumn,
  column = "main",
  compact = false,
}: AiExecuteResultsProps) {
  const [internalBlockOrder, setInternalBlockOrder] = useState<ResultBlockId[]>(DEFAULT_RESULT_BLOCK_ORDER)
  const order = blockOrder ?? internalBlockOrder
  const setBlockOrder = onReorderBlocks ?? setInternalBlockOrder
  const effectiveEnabledBlocks =
    enabledBlocks && enabledBlocks.length > 0 ? enabledBlocks : DEFAULT_RESULT_BLOCK_ORDER
  const columnEnabledBlocks = effectiveEnabledBlocks.filter(
    (blockId) => resolveBlockColumn(blockId, blockColumns ?? {}) === column,
  )
  const [executingAction, setExecutingAction] = useState<string | null>(null)

  const findings = plan?.findings ?? []
  const analysisSections = filterSections(findings, ["summary", "root-cause", "reasoning", "evidence"])
  const resultSections = filterSections(findings, ["actions", "evidence"])
  const preventionSections = filterSections(findings, ["prevention"])
  const steps = plan?.steps ?? fallbackActionPlanSteps
  const suggestedActions = plan?.suggestedActions ?? fallbackSuggestedActionsList
  const confidence = useMemo(() => resolveAnalysisConfidence(plan, job), [plan, job])
  const dataPoints = useMemo(() => resolveConfidenceDataPoints(job, findings), [job, findings])

  const toolCount = job?.result?.tool_call_count ?? job?.result?.toolCallCount ?? 0
  const toolsAvailable = job?.result?.tools_available ?? job?.result?.toolsAvailable ?? 0

  if (error && column === "main") {
    return (
      <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (isProcessing && !plan && column === "main") {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card/60 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-emerald-500" />
        Analyzing and building an execution plan…
      </div>
    )
  }

  if (columnEnabledBlocks.length === 0) {
    return null
  }

  const blocks: Record<ResultBlockId, React.ReactNode> = {
    stats: (
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card/50 px-3 py-2">
        {job?.result ? <ExecutionModeBadge source={job.result} showMeta /> : null}
        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
          {toolCount > 0
            ? `Tools executed · ${toolCount} tool call${toolCount === 1 ? "" : "s"}`
            : isProcessing
              ? "Running analysis"
              : "Analysis ready"}
        </span>
        {toolsAvailable > 0 ? (
          <span className="text-[10px] text-muted-foreground">{toolsAvailable} available</span>
        ) : null}
        <Link
          href="/operator"
          className="ml-auto text-[10px] font-medium text-primary hover:underline"
        >
          Open Command Center
        </Link>
      </div>
    ),
    analysis: analysisSections.length > 0 ? (
      <MesonInsightsPanel
        confidence={confidence}
        confidenceDataPoints={dataPoints}
        severity="high"
        lastUpdated="Just now"
        sections={analysisSections as Parameters<typeof MesonInsightsPanel>[0]["sections"]}
        isGenerating={isProcessing}
        onTryAutoFix={() => toast.info("Auto-fix staged for review")}
        onViewDocumentation={() => window.open("https://docs.gravitre.app", "_blank", "noopener,noreferrer")}
        onContactSupport={() =>
          window.open("mailto:support@gravitre.app?subject=Gravitre%20AI%20help", "_self")
        }
      />
    ) : (
      <EmptyPanel
        title="AI Analysis"
        body="Run a task in Execute mode to populate analysis for what happened and why."
      />
    ),
    results: resultSections.length > 0 ? (
      <MesonInsightsPanel
        confidence={confidence}
        confidenceDataPoints={dataPoints}
        severity="medium"
        lastUpdated="Just now"
        sections={resultSections as Parameters<typeof MesonInsightsPanel>[0]["sections"]}
        isGenerating={isProcessing}
      />
    ) : (
      <EmptyPanel
        title="Results"
        body="Concise outcomes and evidence will appear here after Gravitre finishes the task."
      />
    ),
    prevention: preventionSections.length > 0 ? (
      <MesonInsightsPanel
        confidence={confidence}
        confidenceDataPoints={dataPoints}
        severity="low"
        lastUpdated="Just now"
        sections={preventionSections as Parameters<typeof MesonInsightsPanel>[0]["sections"]}
        isGenerating={isProcessing}
      />
    ) : (
      <EmptyPanel
        title="Prevention"
        body="Future prevention guidance appears here once analysis completes."
      />
    ),
    actions: (
      <SuggestedActions
        actions={suggestedActions}
        isExecuting={executingAction}
        onExecute={(actionId) => {
          setExecutingAction(actionId)
          toast.success("Action submitted for review")
          window.setTimeout(() => setExecutingAction(null), 1200)
        }}
        onSchedule={() => toast.info("Action scheduled for review")}
        onDismiss={() => toast.success("Action dismissed")}
      />
    ),
    plan: (
      <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-card/80 to-card/40 shadow-sm">
        <div className="border-b border-border bg-secondary/30 px-5 py-3">
          <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <ArrowRight className="h-3 w-3" />
            Execution Plan
          </h3>
        </div>
        <div className="space-y-4 p-5">
          {steps.map((step: ActionPlanStep, index: number) => (
            <div key={step.step} className="flex items-start gap-4">
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    step.status === "completed" && "bg-success text-white",
                    step.status === "current" && "bg-info text-white ring-4 ring-info/20",
                    step.status === "pending" && "bg-muted text-muted-foreground",
                  )}
                >
                  {step.status === "completed" ? <CheckCircle className="h-4 w-4" /> : step.step}
                </div>
                {index < steps.length - 1 ? (
                  <div
                    className={cn(
                      "mt-2 h-8 w-0.5",
                      step.status === "completed" ? "bg-success/50" : "bg-border",
                    )}
                  />
                ) : null}
              </div>
              <div className="min-w-0 flex-1 pt-1">
                <p
                  className={cn(
                    "text-sm font-medium",
                    step.status === "current" ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {step.title}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">{step.description}</p>
                {step.status === "current" && isProcessing ? (
                  <div className="mt-2 flex items-center gap-2">
                    <Loader2 className="h-3 w-3 animate-spin text-info" />
                    <span className="text-[10px] font-medium text-info">In Progress</span>
                  </div>
                ) : null}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
            <Button variant="outline" size="sm" className="h-9" asChild>
              <Link href="/operator">
                <Eye className="mr-2 h-3.5 w-3.5" />
                Review in Command Center
              </Link>
            </Button>
            <Button size="sm" className="h-9" onClick={() => toast.info("Execution requires approval")}>
              <Play className="mr-2 h-3.5 w-3.5" />
              Approve & Execute
            </Button>
          </div>
        </div>
      </div>
    ),
  }

  return (
    <DraggableResultStack
      order={order}
      enabledBlocks={columnEnabledBlocks}
      onReorder={setBlockOrder}
      blocks={blocks}
      column={column}
      onMoveBlockToColumn={onMoveBlockToColumn}
      compact={compact}
    />
  )
}
