"use client"

import { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertCircle,
  CheckCircle,
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
import { DataStream } from "@/components/gravitre/premium-effects"
import { useMotionPrefs } from "@/lib/animations"

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

const dotRingColors: Record<StepStatus, string> = {
  completed: "border-success/50 bg-success/10",
  running: "border-info/50 bg-info/10",
  failed: "border-destructive/50 bg-destructive/10",
  pending: "border-border bg-card",
  skipped: "border-border bg-card",
  awaiting_approval: "border-warning/50 bg-warning/10",
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
  index,
  isLast,
  parallelWithNext,
  onRetry,
  isRetrying,
  reduced,
}: {
  step: ExecutionStepView
  index: number
  isLast: boolean
  parallelWithNext?: boolean
  onRetry?: (stepId: string) => void
  isRetrying?: boolean
  reduced: boolean
}) {
  const [expanded, setExpanded] = useState(step.status === "failed")
  const StatusIcon = stepStatusIcons[step.status]
  const isRunning = step.status === "running"
  const isAwaiting = step.status === "awaiting_approval"
  const isCompleted = step.status === "completed"
  const isFailed = step.status === "failed"
  const modelInfo = step.outputSnapshot?.modelInfo ?? step.outputSnapshot?.model_info
  const tokens = step.outputSnapshot?.tokens ?? step.outputSnapshot?.tokenCount

  return (
    <motion.div
      className={cn("p-4", parallelWithNext && "border-r border-border last:border-r-0")}
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 8 }}
      animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={
        reduced
          ? { duration: 0.12 }
          : { type: "spring", stiffness: 380, damping: 32, delay: Math.min(index * 0.05, 0.4) }
      }
    >
      <button
        type="button"
        className="flex w-full items-start gap-4 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        {/* spine column */}
        <div className="relative flex flex-col items-center self-stretch">
          <div className="relative">
            {/* running pulse ring */}
            {isRunning && !reduced ? (
              <motion.span
                className="absolute inset-0 rounded-full border border-info"
                animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
              />
            ) : null}
            {/* awaiting pulse ring */}
            {isAwaiting && !reduced ? (
              <motion.span
                className="absolute inset-0 rounded-full border border-warning"
                animate={{ scale: [1, 1.8], opacity: [0.6, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              />
            ) : null}
            <motion.div
              key={step.status}
              className={cn(
                "relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
                dotRingColors[step.status],
                stepStatusColors[step.status],
              )}
              initial={isCompleted && !reduced ? { scale: 0.4 } : false}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 500, damping: 20 }}
            >
              <StatusIcon className="h-3.5 w-3.5" />
            </motion.div>
          </div>
          {/* connecting spine */}
          {!isLast ? (
            <div className="relative mt-1 w-px flex-1 overflow-hidden bg-border">
              {isRunning ? <DataStream direction="vertical" color="blue" className="opacity-70" /> : null}
            </div>
          ) : null}
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
              {/* duration fades in once completed */}
              <motion.span
                className="font-mono tabular-nums"
                initial={isCompleted && !reduced ? { opacity: 0 } : false}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
              >
                {step.duration}
              </motion.span>
              <motion.span animate={{ rotate: expanded ? 90 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronRight className="h-3.5 w-3.5" />
              </motion.span>
            </div>
          </div>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            key="content"
            initial={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            animate={reduced ? { opacity: 1 } : { height: "auto", opacity: 1 }}
            exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
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
                <motion.div
                  initial={isFailed && !reduced ? { x: 0 } : false}
                  animate={isFailed && !reduced ? { x: [0, -4, 4, -4, 4, 0] } : {}}
                  transition={{ duration: 0.4 }}
                  className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive"
                >
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
                </motion.div>
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
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
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
  const { reduced } = useMotionPrefs()
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

  let renderedIndex = 0

  return (
    <div className="divide-y divide-border">
      {parallelGroups.map((group, groupIndex) => {
        const isParallel = group.length > 1
        const isLastGroup = groupIndex === parallelGroups.length - 1
        return (
          <div key={group.map((s) => s.id).join("-")}>
            {isParallel ? (
              <div className="border-b border-border bg-info/5 px-4 py-2 text-[10px] font-medium uppercase tracking-wider text-info">
                Running in parallel
              </div>
            ) : null}
            <div className={cn(isParallel && "grid grid-cols-1 md:grid-cols-2")}>
              {group.map((step, stepIndex) => {
                const idx = renderedIndex++
                // parallel cells slide in from opposite sides simultaneously
                if (isParallel && !reduced) {
                  return (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, x: stepIndex === 0 ? -24 : 24 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ type: "spring", stiffness: 360, damping: 30 }}
                    >
                      <ExecutionStepRow
                        step={step}
                        index={idx}
                        isLast={isLastGroup}
                        parallelWithNext={stepIndex < group.length - 1}
                        onRetry={onRetryStep}
                        isRetrying={isRetrying}
                        reduced={reduced}
                      />
                    </motion.div>
                  )
                }
                return (
                  <ExecutionStepRow
                    key={step.id}
                    step={step}
                    index={idx}
                    isLast={isLastGroup && stepIndex === group.length - 1}
                    parallelWithNext={isParallel && stepIndex < group.length - 1}
                    onRetry={onRetryStep}
                    isRetrying={isRetrying}
                    reduced={reduced}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
