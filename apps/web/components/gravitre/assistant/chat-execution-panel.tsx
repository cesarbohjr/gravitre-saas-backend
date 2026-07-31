"use client"

import Link from "next/link"
import { ArrowRight, CheckCircle2, Loader2, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"

export type ChatArtifact = {
  artifact_id?: string
  artifactId?: string
  kind?: string
  title?: string
  preview?: string | null
  result_url?: string | null
  resultUrl?: string | null
  mime_type?: string | null
  mimeType?: string | null
  source?: string | null
  integration?: string | null
  metadata?: {
    external_url?: string | null
    externalUrl?: string | null
    runId?: string | null
    conversationId?: string | null
    goal?: string | null
  } | null
}

export type PostActionRecommendation = {
  id?: string
  kind?: string
  title?: string
  reason?: string
  suggestedUtterance?: string
  advisoryOnly?: boolean
  href?: string | null
  confidence?: number
  confidence_is_estimate?: boolean
  confidenceIsEstimate?: boolean
}

export type PostActionFailureBridge = {
  kind?: string
  errorCode?: string
  ctaLabel?: string
  ctaHref?: string
  suggestedUtterance?: string
  prompt?: string
  advisoryOnly?: boolean
}

export type PostActionStepCard = {
  index?: number
  stepId?: string
  label?: string
  success?: boolean
  summary?: string
  evidenceUrl?: string | null
}

export type ChatExecutionResult = {
  success?: boolean
  entity_type?: string
  entity_id?: string
  connector_management_url?: string | null
  result_url?: string | null
  /** Vendor deep link — secondary CTA only when portal-valid. */
  external_url?: string | null
  externalUrl?: string | null
  integration?: string | null
  title?: string
  body?: string
  task_label?: string
  artifacts?: ChatArtifact[] | null
  structured?: {
    external_url?: string | null
    externalUrl?: string | null
    runId?: string | null
    conversationId?: string | null
    goal?: string | null
    whatThisMeans?: string | null
    completionCard?: {
      whatHappened?: string
      whatThisMeans?: string
      vendorUrl?: string | null
      gravitreUrl?: string | null
      success?: boolean
    } | null
    recommendation?: PostActionRecommendation | null
    failureBridge?: PostActionFailureBridge | null
    stepBreakdown?: PostActionStepCard[] | null
    inlinePreview?: boolean
  } | null
  what_this_means?: string | null
  recommendation?: PostActionRecommendation | null
  failure_bridge?: PostActionFailureBridge | null
  business_outcome?: BusinessOutcomeDto | null
  businessOutcome?: BusinessOutcomeDto | null
  /** Wave 7 — structured failure code (e.g. unverifiable_output). */
  error_code?: string | null
  /** Wave 7 — calibrated uncertainty notes from trust envelope. */
  assumption_notes?: string[] | null
}

function resolveBusinessOutcome(executionResult: ChatExecutionResult): BusinessOutcomeDto | null {
  const candidate =
    executionResult.business_outcome ||
    executionResult.businessOutcome ||
    (executionResult.structured as { businessOutcome?: BusinessOutcomeDto } | null | undefined)
      ?.businessOutcome ||
    null
  if (candidate && typeof candidate === "object" && candidate.id && candidate.projection === "business_outcome") {
    return candidate
  }
  if (candidate && typeof candidate === "object" && candidate.id) {
    return { ...candidate, projection: candidate.projection || "business_outcome" }
  }
  return null
}

export type OrchestrationStepPreview = {
  step_id?: string
  label?: string
  kind?: string
  supported?: boolean
  requires_approval?: boolean
  skip_reason?: string
}

export type ChatPendingTask = {
  type?: string
  status?: string
  params?: {
    goal?: string
    total_steps?: number
    current_step_index?: number
    steps?: OrchestrationStepPreview[]
    label?: string
    invoke_action?: string
    kind?: string
  }
  current_step?: OrchestrationStepPreview
}

type ChatExecutionPanelProps = {
  dialogueMode?: string | null
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  confirming?: boolean
  onConfirm?: () => void
  /** Admin/owner (or policy approver) — show Approve button; others see queued copy. */
  canApprove?: boolean
  className?: string
}

function pendingLabel(pendingTask: ChatPendingTask): string {
  const params = pendingTask.params
  if (pendingTask.type === "connector_orchestration") {
    if (pendingTask.status === "awaiting_step_confirm" && pendingTask.current_step?.label) {
      return pendingTask.current_step.label
    }
    if (params?.goal) return params.goal.slice(0, 120)
    return "Multi-step orchestration"
  }
  if (!params || typeof params !== "object") return "this action"
  if (typeof params.label === "string" && params.label.trim()) return params.label
  if (typeof params.invoke_action === "string") return params.invoke_action
  return "this action"
}

function pendingDescription(pendingTask: ChatPendingTask): string {
  if (pendingTask.type === "connector_orchestration") {
    const params = pendingTask.params
    const total = params?.total_steps ?? params?.steps?.length ?? 0
    if (pendingTask.status === "awaiting_step_confirm") {
      const index = (params?.current_step_index ?? 0) + 1
      const action = pendingTask.current_step?.label || pendingLabel(pendingTask)
      return `Step ${index} of ${total}: approve **${action}** before Gravitre runs it in your connected apps.`
    }
    return (
      `Gravitre will run ${total} steps across your connected apps. ` +
      "Read steps run automatically; write steps run automatically unless your approval settings require confirmation."
    )
  }
  if (pendingTask.type === "connector_action") {
    const params = pendingTask.params
    const action =
      params && typeof params.invoke_action === "string" ? params.invoke_action : "connector action"
    const kind = params && typeof params.kind === "string" ? params.kind : "write"
    return `Gravitre will run ${action} (${kind} action) through your connected integration after you approve.`
  }
  if (pendingTask.type === "create_agent") {
    return "Gravitre will create your agent and notify you when it is ready."
  }
  return "Gravitre will create a draft workflow you can open in the builder."
}

function confirmButtonLabel(pendingTask: ChatPendingTask, confirming: boolean): string {
  if (confirming) {
    if (pendingTask.type === "connector_orchestration") {
      return pendingTask.status === "awaiting_step_confirm" ? "Running step…" : "Starting…"
    }
    return pendingTask.type === "connector_action" ? "Running…" : "Creating…"
  }
  if (pendingTask.type === "connector_orchestration") {
    return pendingTask.status === "awaiting_step_confirm" ? "Approve step" : "Approve plan"
  }
  if (pendingTask.type === "connector_action") return "Approve and run"
  return "Confirm and create"
}

function StepBadge({ label, tone }: { label: string; tone: "read" | "write" | "skipped" | "warning" }) {
  const styles = {
    read: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    write: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
    skipped: "border-muted-foreground/20 bg-muted/40 text-muted-foreground",
    warning: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-400",
  }[tone]
  return (
    <span className={cn("ml-1 inline-flex rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide", styles)}>
      {label}
    </span>
  )
}

function OrchestrationStepList({ steps }: { steps: OrchestrationStepPreview[] }) {
  if (!steps.length) return null
  return (
    <ol className="mt-2 space-y-2 text-xs text-muted-foreground">
      {steps.map((step, index) => (
        <li key={step.step_id || index} className="flex gap-2">
          <span className="font-medium text-foreground/80">{index + 1}.</span>
          <span className="min-w-0 flex-1">
            <span className="text-foreground/90">{step.label || "Step"}</span>
            {step.supported === false ? (
              <StepBadge label="skipped" tone="skipped" />
            ) : step.kind === "read" ? (
              <StepBadge label="read auto" tone="read" />
            ) : (
              <StepBadge label="needs approval" tone="write" />
            )}
            {step.skip_reason ? (
              <p className="mt-0.5 text-[11px] text-orange-700 dark:text-orange-400">{step.skip_reason}</p>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  )
}

function isExternalUrl(url: string): boolean {
  return url.startsWith("http://") || url.startsWith("https://")
}

function isPortalScopedHubspotUrl(url: string): boolean {
  if (!url.startsWith("https://app.hubspot.com/contacts/")) return false
  const hub = url.slice("https://app.hubspot.com/contacts/".length).split("/")[0]
  return /^\d+$/.test(hub || "")
}

function resultLinkLabel(executionResult: ChatExecutionResult, href?: string | null): string {
  const url = (href || executionResult.result_url || "").trim()
  if (url.startsWith("/runs/")) return "View run"
  if (url.startsWith("/ai")) return "View in Gravitre"
  if (executionResult.entity_type === "agent") return "Open agent"
  if (executionResult.entity_type === "workflow") return "Open in builder"
  if (executionResult.entity_type === "run" || executionResult.entity_type === "workflow_run") {
    return "View run"
  }
  if (executionResult.integration && isExternalUrl(url)) {
    const normalized = executionResult.integration.trim()
    if (normalized) {
      return `Open in ${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}`
    }
  }
  return "View in Gravitre"
}

function resolveExternalUrl(executionResult: ChatExecutionResult, artifact?: ChatArtifact): string | null {
  const candidates = [
    executionResult.external_url,
    executionResult.externalUrl,
    executionResult.structured?.external_url,
    executionResult.structured?.externalUrl,
    artifact?.metadata?.external_url,
    artifact?.metadata?.externalUrl,
  ]
  for (const value of candidates) {
    const url = (value || "").trim()
    if (!url || !isExternalUrl(url)) continue
    if (url.includes("app.hubspot.com") && !isPortalScopedHubspotUrl(url)) continue
    return url
  }
  return null
}

function artifactHref(artifact: ChatArtifact): string | null {
  return artifact.result_url || artifact.resultUrl || null
}

function ArtifactCards({ artifacts }: { artifacts: ChatArtifact[] }) {
  if (!artifacts.length) return null
  return (
    <div className="mt-3 space-y-2">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Artifacts</p>
      {artifacts.slice(0, 6).map((artifact) => {
        const href = artifactHref(artifact)
        const title = artifact.title || artifact.kind || "Artifact"
        const preview = artifact.preview?.trim()
        return (
          <div
            key={artifact.artifact_id || artifact.artifactId || title}
            className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-xs"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{title}</span>
              {artifact.kind ? (
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {artifact.kind}
                </span>
              ) : null}
            </div>
            {preview ? <p className="mt-1 line-clamp-3 text-muted-foreground">{preview}</p> : null}
            {href ? (
              <div className="mt-2 flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline" className="h-7 text-xs">
                  {isExternalUrl(href) ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      Open artifact
                      <ArrowRight className="ml-1.5 h-3 w-3" />
                    </a>
                  ) : (
                    <Link href={href}>
                      Open artifact
                      <ArrowRight className="ml-1.5 h-3 w-3" />
                    </Link>
                  )}
                </Button>
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export function ChatExecutionPanel({
  dialogueMode,
  executionResult,
  pendingTask,
  confirming = false,
  onConfirm,
  canApprove = false,
  className,
}: ChatExecutionPanelProps) {
  if (executionResult && executionResult.success === false) {
    const businessOutcome = resolveBusinessOutcome(executionResult)
    if (businessOutcome) {
      return <BusinessOutcomeView outcome={businessOutcome} density="chat" className={className} />
    }
    const code = executionResult.error_code
    const unverifiable = code === "unverifiable_output"
    const bridge =
      executionResult.failure_bridge ||
      executionResult.structured?.failureBridge ||
      null
    // Missing params are a clarify problem, not a connectors outage — never default
    // to "Open connectors" for validation_error (Claude/Manus-honest recovery).
    const validationError = code === "validation_error"
    const ctaHref =
      bridge?.ctaHref ||
      (validationError ? "/ai" : null) ||
      executionResult.connector_management_url ||
      "/connectors"
    const ctaLabel =
      bridge?.ctaLabel ||
      (validationError ? "Adjust parameters" : null) ||
      "Open connectors"
    return (
      <div
        className={cn(
          "mt-3 rounded-xl border px-4 py-3 text-sm",
          unverifiable
            ? "border-amber-500/25 bg-amber-500/5"
            : "border-red-500/25 bg-red-500/5",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <ShieldAlert
            className={cn(
              "mt-0.5 h-4 w-4 shrink-0",
              unverifiable ? "text-amber-600" : "text-red-600",
            )}
          />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-foreground">
              {executionResult.task_label || executionResult.title || "Action did not complete"}
            </p>
            {code ? (
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">{code}</p>
            ) : null}
            {executionResult.body ? (
              <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                {executionResult.body}
              </p>
            ) : null}
            {bridge?.prompt ? (
              <p className="mt-2 text-xs text-foreground/90">{bridge.prompt}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button asChild size="sm" className="h-8">
                {isExternalUrl(ctaHref) ? (
                  <a href={ctaHref} target="_blank" rel="noopener noreferrer">
                    {ctaLabel}
                    <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                  </a>
                ) : (
                  <Link href={ctaHref}>
                    {ctaLabel}
                    <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                  </Link>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (executionResult?.success) {
    const businessOutcome = resolveBusinessOutcome(executionResult)
    if (businessOutcome) {
      return <BusinessOutcomeView outcome={businessOutcome} density="chat" className={className} />
    }
    const resultUrl = executionResult.result_url
    const artifacts = (executionResult.artifacts || []).filter(
      (row) => row && (row.title || row.preview || row.result_url || row.resultUrl),
    )
    const assumptions = (executionResult.assumption_notes || []).filter(
      (note) => typeof note === "string" && note.trim(),
    )
    const whatThisMeans =
      executionResult.what_this_means ||
      executionResult.structured?.whatThisMeans ||
      executionResult.structured?.completionCard?.whatThisMeans ||
      null
    const recommendation =
      executionResult.recommendation ||
      executionResult.structured?.recommendation ||
      null
    const steps = executionResult.structured?.stepBreakdown || []
    const isPreview = Boolean(executionResult.structured?.inlinePreview)
    return (
      <div
        className={cn(
          "mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-foreground">
              {isPreview
                ? "Live vendor preview"
                : executionResult.task_label || executionResult.title || "Task completed"}
            </p>
            {executionResult.body ? (
              <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">{executionResult.body}</p>
            ) : null}
            {whatThisMeans ? (
              <p className="mt-2 text-xs text-foreground/90">
                <span className="font-medium">What this means: </span>
                {whatThisMeans}
              </p>
            ) : (
              <p className="mt-2 text-[11px] text-muted-foreground">
                {resultUrl
                  ? "Verified — open the run overview for a durable audit trail."
                  : "Completed with inline summary only (no deep link returned)."}
              </p>
            )}
            {steps.length > 1 ? (
              <ol className="mt-2 space-y-1.5 text-xs text-muted-foreground">
                {steps.map((step) => (
                  <li key={step.stepId || step.index} className="flex gap-2">
                    <span className="font-medium text-foreground/80">{step.index}.</span>
                    <span className="min-w-0 flex-1">
                      <span className="text-foreground/90">
                        {step.success === false ? "○" : "✓"} {step.label || "Step"}
                      </span>
                      {step.summary ? (
                        <p className="mt-0.5 line-clamp-3">{step.summary}</p>
                      ) : null}
                      {step.evidenceUrl ? (
                        <p className="mt-0.5 truncate text-[11px]">{step.evidenceUrl}</p>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ol>
            ) : null}
            {recommendation?.title ? (
              <div className="mt-2 rounded-lg border border-border/60 bg-background/60 px-2.5 py-2 text-[11px]">
                <p className="font-medium text-foreground">What I&apos;d look at next</p>
                <p className="mt-0.5 text-muted-foreground">
                  {recommendation.title}
                  {recommendation.reason ? ` — ${recommendation.reason}` : ""}
                </p>
                {recommendation.suggestedUtterance ? (
                  <p className="mt-1 text-foreground/80">
                    Suggest only — say &ldquo;{recommendation.suggestedUtterance}&rdquo; to proceed.
                  </p>
                ) : null}
              </div>
            ) : null}
            {assumptions.length > 0 ? (
              <div className="mt-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-2.5 py-2 text-[11px] text-amber-900 dark:text-amber-200">
                <p className="font-medium">Assumptions</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {assumptions.slice(0, 4).map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <ArtifactCards artifacts={artifacts} />
            {resultUrl || resolveExternalUrl(executionResult) ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {resultUrl ? (
                  <Button asChild size="sm" className="h-8">
                    {isExternalUrl(resultUrl) ? (
                      <a href={resultUrl} target="_blank" rel="noopener noreferrer">
                        {resultLinkLabel(executionResult, resultUrl)}
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <Link href={resultUrl}>
                        {resultLinkLabel(executionResult, resultUrl)}
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </Link>
                    )}
                  </Button>
                ) : null}
                {(() => {
                  const external = resolveExternalUrl(executionResult)
                  if (!external) return null
                  const vendor = (executionResult.integration || "source").trim()
                  const label = vendor
                    ? `Open in ${vendor.charAt(0).toUpperCase()}${vendor.slice(1)}`
                    : "Open in source"
                  return (
                    <Button asChild size="sm" variant="outline" className="h-8">
                      <a href={external} target="_blank" rel="noopener noreferrer">
                        {label}
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </a>
                    </Button>
                  )
                })()}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  if (
    (dialogueMode === "confirm" || dialogueMode === "awaiting_approval") &&
    pendingTask?.type
  ) {
    const isConnector = pendingTask.type === "connector_action"
    const isOrchestration = pendingTask.type === "connector_orchestration"
    const needsApproval = isConnector || isOrchestration
    // Trust server dialogue_mode: "confirm" means this user may approve (HITL roles/users).
    // "awaiting_approval" means the request was queued for configured approvers.
    const queuedForApprover =
      dialogueMode === "awaiting_approval" ||
      pendingTask.status === "awaiting_admin_approval" ||
      (dialogueMode === "confirm" && !canApprove && pendingTask.status !== "awaiting_confirm")
    return (
      <div
        className={cn(
          "mt-3 rounded-xl border px-4 py-3 text-sm",
          needsApproval ? "border-amber-500/25 bg-amber-500/5" : "border-info/20 bg-info/5",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          {needsApproval ? (
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          ) : null}
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "text-xs font-medium uppercase tracking-wide",
                needsApproval ? "text-amber-700 dark:text-amber-400" : "text-info",
              )}
            >
              {queuedForApprover
                ? "Pending approval"
                : isOrchestration
                  ? pendingTask.status === "awaiting_step_confirm"
                    ? "Step approval required"
                    : "Orchestration plan"
                  : isConnector
                    ? "Approval required"
                    : "Ready to execute"}
            </p>
            {(isConnector || pendingTask.status === "awaiting_step_confirm") && (
              <p className="mt-1 text-sm font-medium text-foreground">{pendingLabel(pendingTask)}</p>
            )}
            {isConnector && pendingTask.params?.kind ? (
              <div className="mt-1">
                <StepBadge
                  label={pendingTask.params.kind === "read" ? "read auto" : "needs approval"}
                  tone={pendingTask.params.kind === "read" ? "read" : "write"}
                />
              </div>
            ) : null}
            <p className="mt-1 text-xs text-muted-foreground">{pendingDescription(pendingTask)}</p>
            {isOrchestration && pendingTask.status === "awaiting_plan_confirm" ? (
              <OrchestrationStepList steps={pendingTask.params?.steps ?? []} />
            ) : null}
            {queuedForApprover ? (
              <p className="mt-3 text-sm text-foreground">
                Your request will be sent for approval.
              </p>
            ) : onConfirm ? (
              <Button
                size="sm"
                className="mt-3 h-8"
                disabled={confirming}
                onClick={onConfirm}
              >
                {confirming ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    {confirmButtonLabel(pendingTask, true)}
                  </>
                ) : (
                  confirmButtonLabel(pendingTask, false)
                )}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  return null
}
