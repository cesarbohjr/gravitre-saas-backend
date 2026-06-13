"use client"

import { useMemo, useState } from "react"
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  GitBranch,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  TerminalSquare,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type StepStatus =
  | "completed"
  | "running"
  | "failed"
  | "pending"
  | "skipped"
  | "awaiting_approval"

export interface ExecutionStepView {
  id: string
  name: string
  stepType?: string
  status: StepStatus
  duration: string
  startedAt: string
  logs?: string[]
  errorMessage?: string | null
  inputSnapshot?: Record<string, unknown> | null
  outputSnapshot?: Record<string, unknown> | null
  isRetryable?: boolean
}

const stepStatusIcons = {
  completed: CheckCircle,
  running: Play,
  failed: AlertCircle,
  pending: Clock,
  skipped: Pause,
  awaiting_approval: Clock,
}

const stepStatusColors: Record<StepStatus, string> = {
  completed: "text-success",
  running: "text-info",
  failed: "text-destructive",
  pending: "text-muted-foreground",
  skipped: "text-muted-foreground line-through",
  awaiting_approval: "text-warning",
}

function JsonBlock({ label, value }: { label: string; value: Record<string, unknown> | null | undefined }) {
  if (!value || Object.keys(value).length === 0) return null
  return (
    <div className="rounded-md bg-muted/50 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-muted-foreground">
        <TerminalSquare className="h-3 w-3" />
        <span className="text-[10px] font-medium uppercase tracking-wider">{label}</span>
      </div>
      <pre className="max-h-48 overflow-auto font-mono text-[11px] text-muted-foreground whitespace-pre-wrap">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

function BranchVisualization({ output }: { output?: Record<string, unknown> | null }) {
  const branch = String(output?.branch ?? output?.selectedBranch ?? "")
  if (!branch) return null
  const options = ["true", "false", "high", "medium", "low", "primary", "alternate"]
  const labels = options.filter((opt) => opt !== branch.toLowerCase()).slice(0, 2)
  return (
    <div className="mt-3 flex items-center gap-2">
      <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
      <div className="flex items-center gap-2">
        <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-medium text-emerald-600">
          {branch}
        </span>
        {labels.map((label) => (
          <span
            key={label}
            className="rounded-md border border-border px-2 py-1 text-[10px] text-muted-foreground/50 line-through"
          >
            {label}
          </span>
        ))}
      </div>
    </div>
  )
}

function ExecutionStepRow({
  step,
  parallelWithNext,
  onRetry,
  isRetrying,
}: {
  step: ExecutionStepView
  parallelWithNext?: boolean
  onRetry?: (stepId: string) => void
  isRetrying?: boolean
}) {
  const [expanded, setExpanded] = useState(step.status === "failed")
  const StatusIcon = stepStatusIcons[step.status]
  const isRunning = step.status === "running"
  const isAwaiting = step.status === "awaiting_approval"
  const modelInfo = step.outputSnapshot?.modelInfo ?? step.outputSnapshot?.model_info
  const tokens = step.outputSnapshot?.tokens ?? step.outputSnapshot?.tokenCount

  return (
    <div className={cn("p-4", parallelWithNext && "border-r border-border last:border-r-0")}>
      <button
        type="button"
        className="flex w-full items-start gap-4 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div
          className={cn(
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border",
            stepStatusColors[step.status],
            isRunning && "animate-pulse",
            isAwaiting && "animate-pulse border-warning/50 bg-warning/10",
          )}
        >
          <StatusIcon className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <h3 className={cn("text-sm font-medium text-foreground", step.status === "skipped" && "line-through")}>
                {step.name}
              </h3>
              {step.stepType ? (
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{step.stepType}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
              <span>{step.startedAt}</span>
              <span className="font-mono">{step.duration}</span>
              {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </div>
          </div>
        </div>
      </button>

      {expanded ? (
        <div className="ml-10 mt-3 space-y-3">
          <JsonBlock label="Input" value={step.inputSnapshot} />
          <JsonBlock label="Output" value={step.outputSnapshot} />
          {(step.stepType === "condition" || step.stepType === "decision") && (
            <BranchVisualization output={step.outputSnapshot} />
          )}
          {modelInfo || tokens ? (
            <p className="text-[11px] text-muted-foreground">
              {modelInfo ? `Model: ${JSON.stringify(modelInfo)}` : null}
              {modelInfo && tokens ? " · " : null}
              {tokens ? `Tokens: ${String(tokens)}` : null}
            </p>
          ) : null}
          {step.errorMessage ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
              {step.errorMessage}
              {step.status === "failed" && onRetry ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 h-7 gap-1.5"
                  disabled={isRetrying}
                  onClick={() => onRetry(step.id)}
                >
                  {isRetrying ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  Retry step
                </Button>
              ) : null}
            </div>
          ) : null}
          {step.logs && step.logs.length > 0 && (
            <div className="rounded-md bg-muted/50 p-3">
              <div className="mb-2 flex items-center gap-1.5 text-muted-foreground">
                <TerminalSquare className="h-3 w-3" />
                <span className="text-[10px] font-medium uppercase tracking-wider">Logs</span>
              </div>
              <div className="space-y-1 font-mono text-xs">
                {step.logs.map((log, i) => (
                  <p key={i} className={log.startsWith("ERROR") ? "text-destructive" : "text-muted-foreground"}>
                    {log}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

export function ExecutionTimeline({
  steps,
  onRetryStep,
  isRetrying,
}: {
  steps: ExecutionStepView[]
  onRetryStep?: (stepId: string) => void
  isRetrying?: boolean
}) {
  const parallelGroups = useMemo(() => {
    const groups: ExecutionStepView[][] = []
    let i = 0
    while (i < steps.length) {
      const current = steps[i]
      const next = steps[i + 1]
      if (
        current.status === "running" &&
        next?.status === "running" &&
        current.startedAt !== "-" &&
        current.startedAt === next.startedAt
      ) {
        groups.push([current, next])
        i += 2
        continue
      }
      groups.push([current])
      i += 1
    }
    return groups
  }, [steps])

  if (steps.length === 0) {
    return <div className="p-4 text-sm text-muted-foreground">Waiting for step output…</div>
  }

  return (
    <div className="divide-y divide-border">
      {parallelGroups.map((group, groupIndex) => {
        const isParallel = group.length > 1
        return (
          <div key={group.map((s) => s.id).join("-")}>
            {isParallel ? (
              <div className="border-b border-border bg-info/5 px-4 py-2 text-[10px] font-medium uppercase tracking-wider text-info">
                Running in parallel
              </div>
            ) : null}
            <div className={cn(isParallel && "grid grid-cols-1 md:grid-cols-2")}>
              {group.map((step, stepIndex) => (
                <ExecutionStepRow
                  key={step.id}
                  step={step}
                  parallelWithNext={isParallel && stepIndex < group.length - 1}
                  onRetry={onRetryStep}
                  isRetrying={isRetrying}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
