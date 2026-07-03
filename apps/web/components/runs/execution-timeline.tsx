"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  AlertCircle,
  CheckCircle,
  ChevronRight,
  Clock,
  ExternalLink,
  GitBranch,
  Loader2,
  Pause,
  Play,
  PlugZap,
  RefreshCw,
  TerminalSquare,
  XCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { readExecutionModeFields } from "@/lib/execution-mode"
import { cn } from "@/lib/utils"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { DataStream } from "@/components/gravitre/premium-effects"
import { useMotionPrefs } from "@/lib/animations"
import {
  humanizeConnectorAction,
  humanizeLogLine,
  summarizeStepError,
  summarizeStepPayload,
} from "@/lib/runs/step-summary"

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

const SECRET_KEY_PATTERN = /(token|secret|password|api[_-]?key|authorization|bearer|credential|access[_-]?key|client[_-]?secret|refresh)/i

function redactSecrets(value: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null
  const out: Record<string, unknown> = {}
  for (const [key, val] of Object.entries(value)) {
    if (SECRET_KEY_PATTERN.test(key)) {
      out[key] = "••••••• (redacted)"
    } else if (val && typeof val === "object" && !Array.isArray(val)) {
      out[key] = redactSecrets(val as Record<string, unknown>)
    } else {
      out[key] = val
    }
  }
  return out
}

function firstString(...values: unknown[]): string | undefined {
  for (const v of values) {
    if (typeof v === "string" && v.trim()) return v.trim()
  }
  return undefined
}

export interface InvokeToolMeta {
  isInvokeTool: boolean
  action?: string
  vendor?: string
  actionName?: string
  connectorId?: string
  errorCode?: string
  success?: boolean
  retryCount?: number
  isAuthError: boolean
}

const AUTH_ERROR_PATTERN = /(auth|unauthorized|forbidden|token|credential|expired|401|403|reconnect)/i

// Derives connector tool metadata from a step's type + output snapshot. The
// backend InvokeToolHandler writes action ("{vendor}.{action}"), connector_id,
// success, error_code and retry_count into the step output.
function parseInvokeTool(step: ExecutionStepView): InvokeToolMeta {
  const out = step.outputSnapshot ?? {}
  const input = step.inputSnapshot ?? {}
  const action = firstString(
    out.action,
    (out.config as Record<string, unknown> | undefined)?.action,
    input.action,
    (input.config as Record<string, unknown> | undefined)?.action,
  )
  const isInvokeTool = step.stepType === "invoke_tool" || Boolean(action)
  if (!isInvokeTool) return { isInvokeTool: false, isAuthError: false }

  const [vendor, ...rest] = (action ?? "").split(".")
  const errorCode = firstString(out.error_code, out.errorCode, (out.error as Record<string, unknown> | undefined)?.code)
  const successRaw = out.success
  const success = typeof successRaw === "boolean" ? successRaw : step.status === "completed" ? true : undefined
  const retryRaw = out.retry_count ?? out.retryCount ?? out.attempts
  const retryCount = typeof retryRaw === "number" ? retryRaw : undefined
  const isAuthError =
    step.status === "failed" &&
    Boolean((errorCode && AUTH_ERROR_PATTERN.test(errorCode)) || (step.errorMessage && AUTH_ERROR_PATTERN.test(step.errorMessage)))

  return {
    isInvokeTool: true,
    action,
    vendor: vendor || undefined,
    actionName: rest.length ? rest.join(".") : undefined,
    connectorId: firstString(out.connector_id, out.connectorId, input.connector_id, input.connectorId),
    errorCode,
    success,
    retryCount,
    isAuthError,
  }
}

function PayloadSummary({
  label,
  value,
}: {
  label: string
  value: Record<string, unknown> | null | undefined
}) {
  const [showRaw, setShowRaw] = useState(false)
  const summary = useMemo(() => summarizeStepPayload(value), [value])
  if (!value || Object.keys(value).length === 0) return null

  return (
    <div className="rounded-md bg-muted/50 p-3">
      <div className="mb-2 flex items-center justify-between gap-2 text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <TerminalSquare className="h-3 w-3" />
          <span className="text-[10px] font-medium uppercase tracking-wider">{label}</span>
        </div>
        <button
          type="button"
          onClick={() => setShowRaw((open) => !open)}
          className="text-[10px] font-medium text-muted-foreground hover:text-foreground"
        >
          {showRaw ? "Hide raw data" : "Raw data"}
        </button>
      </div>
      {summary ? (
        <div className="space-y-1 text-sm text-foreground">
          <p>{summary.summary}</p>
          {summary.bullets.map((bullet) => (
            <p key={bullet} className="text-xs text-muted-foreground">
              {bullet}
            </p>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No meaningful input was recorded for this step.</p>
      )}
      {showRaw ? (
        <pre className="mt-2 max-h-48 overflow-auto font-mono text-[11px] text-muted-foreground whitespace-pre-wrap">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : null}
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
        <span className="rounded-md border border-success/30 bg-success/10 px-2 py-1 text-[10px] font-medium text-success">
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

function InvokeToolDetail({ meta }: { meta: InvokeToolMeta }) {
  const succeeded = meta.success === true
  const failed = meta.success === false
  const actionLabel = humanizeConnectorAction(meta.action)
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-muted-foreground">
        <PlugZap className="h-3 w-3" />
        <span className="text-[10px] font-medium uppercase tracking-wider">Connector result</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[11px]">
        {actionLabel ? (
          <div className="col-span-2">
            <dt className="text-muted-foreground">What ran</dt>
            <dd className="mt-0.5 text-foreground">{actionLabel}</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-muted-foreground">Result</dt>
          <dd className="mt-0.5">
            {succeeded ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-success/30 bg-success/10 px-1.5 py-0.5 font-medium text-success">
                <CheckCircle className="h-3 w-3" /> Success
              </span>
            ) : failed ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-destructive/30 bg-destructive/10 px-1.5 py-0.5 font-medium text-destructive">
                <XCircle className="h-3 w-3" /> Failed
              </span>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </dd>
        </div>
        {meta.errorCode ? (
          <div>
            <dt className="text-muted-foreground">Issue</dt>
            <dd className="mt-0.5 text-destructive">{meta.errorCode.replace(/_/g, " ")}</dd>
          </div>
        ) : null}
        {typeof meta.retryCount === "number" ? (
          <div>
            <dt className="text-muted-foreground">Retries</dt>
            <dd className="mt-0.5 font-mono text-foreground">{meta.retryCount}</dd>
          </div>
        ) : null}
        {meta.connectorId ? (
          <div className="col-span-2">
            <dt className="text-muted-foreground">Connector</dt>
            <dd className="mt-0.5">
              <Link
                href={`/connectors/${meta.connectorId}`}
                className="inline-flex items-center gap-1 text-info hover:underline"
              >
                Open connector settings
                <ExternalLink className="h-3 w-3" />
              </Link>
            </dd>
          </div>
        ) : null}
      </dl>
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
  expanded,
  onToggleExpanded,
  isHighlighted,
}: {
  step: ExecutionStepView
  index: number
  isLast: boolean
  parallelWithNext?: boolean
  onRetry?: (stepId: string) => void
  isRetrying?: boolean
  reduced: boolean
  expanded: boolean
  onToggleExpanded: () => void
  isHighlighted?: boolean
}) {
  const StatusIcon = stepStatusIcons[step.status]
  const isRunning = step.status === "running"
  const isAwaiting = step.status === "awaiting_approval"
  const isCompleted = step.status === "completed"
  const isFailed = step.status === "failed"
  const modelInfo = step.outputSnapshot?.modelInfo ?? step.outputSnapshot?.model_info
  const tokens = step.outputSnapshot?.tokens ?? step.outputSnapshot?.tokenCount
  const invokeMeta = useMemo(() => parseInvokeTool(step), [step])
  const errorSummary = useMemo(() => summarizeStepError(step.errorMessage), [step.errorMessage])
  const connectorActionLabel = humanizeConnectorAction(invokeMeta.action)
  const executionModeSource = useMemo(
    () => (step.stepType === "agent" ? step.outputSnapshot : null),
    [step.outputSnapshot, step.stepType],
  )
  const executionMode = useMemo(
    () => readExecutionModeFields(executionModeSource as Record<string, unknown> | null),
    [executionModeSource],
  )

  return (
    <motion.div
      className={cn(
        "p-4",
        parallelWithNext && "border-r border-border last:border-r-0",
        isHighlighted && "bg-info/5 ring-1 ring-inset ring-info/20",
      )}
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
        onClick={onToggleExpanded}
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
            <div className="flex min-w-0 items-center gap-2.5">
              {invokeMeta.isInvokeTool && invokeMeta.vendor ? (
                <ConnectorIcon
                  vendor={invokeMeta.vendor}
                  size="xs"
                  showStatusIndicator={false}
                  status={invokeMeta.success === false ? "error" : "connected"}
                />
              ) : null}
              <div className="min-w-0">
                <h3 className={cn("text-sm font-medium text-foreground", step.status === "skipped" && "line-through")}>
                  {step.name}
                </h3>
                {connectorActionLabel ? (
                  <p className="text-[11px] text-muted-foreground">{connectorActionLabel}</p>
                ) : step.stepType ? (
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {step.stepType === "invoke_tool" ? "Connector step" : titleCaseStepType(step.stepType)}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
              {executionMode.mode ? (
                <ExecutionModeBadge source={executionModeSource as Record<string, unknown>} compact />
              ) : null}
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
              {invokeMeta.isInvokeTool ? <InvokeToolDetail meta={invokeMeta} /> : null}
              <PayloadSummary
                label="Input"
                value={invokeMeta.isInvokeTool ? redactSecrets(step.inputSnapshot) : step.inputSnapshot}
              />
              <PayloadSummary
                label="Output"
                value={invokeMeta.isInvokeTool ? redactSecrets(step.outputSnapshot) : step.outputSnapshot}
              />
              {(step.stepType === "condition" || step.stepType === "decision") && (
                <BranchVisualization output={step.outputSnapshot} />
              )}
              {modelInfo || tokens ? (
                <p className="text-[11px] text-muted-foreground">
                  {modelInfo ? "An AI model handled this step." : null}
                  {modelInfo && tokens ? " · " : null}
                  {tokens ? `${String(tokens)} tokens used` : null}
                </p>
              ) : null}
              {errorSummary ? (
                <motion.div
                  initial={isFailed && !reduced ? { x: 0 } : false}
                  animate={isFailed && !reduced ? { x: [0, -4, 4, -4, 4, 0] } : {}}
                  transition={{ duration: 0.4 }}
                  className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                >
                  <p className="font-medium">{errorSummary.title}</p>
                  {errorSummary.fix ? (
                    <p className="mt-2 text-xs text-destructive/90">{errorSummary.fix}</p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {step.status === "failed" && onRetry ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1.5"
                        disabled={isRetrying}
                        onClick={() => onRetry(step.id)}
                      >
                        {isRetrying ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                        Retry step
                      </Button>
                    ) : null}
                    {invokeMeta.isAuthError && invokeMeta.connectorId ? (
                      <Button asChild variant="outline" size="sm" className="h-7 gap-1.5">
                        <Link href={`/connectors/${invokeMeta.connectorId}`}>
                          <PlugZap className="h-3 w-3" />
                          Reconnect connector
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </motion.div>
              ) : null}
              {step.logs && step.logs.length > 0 && (
                <div className="rounded-md bg-muted/50 p-3">
                  <div className="mb-2 flex items-center gap-1.5 text-muted-foreground">
                    <TerminalSquare className="h-3 w-3" />
                    <span className="text-[10px] font-medium uppercase tracking-wider">Activity</span>
                  </div>
                  <div className="space-y-1 text-xs">
                    {step.logs.map((log, i) => (
                      <p key={i} className={log.startsWith("ERROR") ? "text-destructive" : "text-muted-foreground"}>
                        {humanizeLogLine(log)}
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

function titleCaseStepType(value: string): string {
  return value
    .replace(/_/g, " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
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
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      for (const step of steps) {
        if (
          step.status === "running" ||
          step.status === "failed" ||
          step.status === "awaiting_approval"
        ) {
          next.add(step.id)
        }
      }
      return next
    })
  }, [steps])

  const toggleStep = (stepId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(stepId)) next.delete(stepId)
      else next.add(stepId)
      return next
    })
  }

  const expandAll = () => setExpandedIds(new Set(steps.map((step) => step.id)))
  const collapseAll = () => setExpandedIds(new Set())

  const activeStepId = useMemo(() => {
    const running = steps.find((step) => step.status === "running")
    if (running) return running.id
    const awaiting = steps.find((step) => step.status === "awaiting_approval")
    if (awaiting) return awaiting.id
    const failed = steps.find((step) => step.status === "failed")
    return failed?.id
  }, [steps])

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
    <div>
      {steps.length > 0 ? (
        <div className="flex items-center justify-end gap-2 border-b border-border px-4 py-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={expandAll}>
            Expand all
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={collapseAll}>
            Collapse all
          </Button>
        </div>
      ) : null}
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
                        expanded={expandedIds.has(step.id)}
                        onToggleExpanded={() => toggleStep(step.id)}
                        isHighlighted={step.id === activeStepId}
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
                    expanded={expandedIds.has(step.id)}
                    onToggleExpanded={() => toggleStep(step.id)}
                    isHighlighted={step.id === activeStepId}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
      </div>
    </div>
  )
}
