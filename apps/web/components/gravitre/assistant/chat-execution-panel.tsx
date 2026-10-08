"use client"

import Link from "next/link"
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  ShieldAlert,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { HIGHLIGHT } from "@/lib/design-system"
import { PlanApprovalChrome } from "@/components/gravitre/agent-ui/plan-approval-chrome"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"
import {
  FileReferenceChip,
  FileReferenceChipRow,
  hostedFilesFromUnknown,
} from "@/components/gravitre/assistant/file-reference-chip"
import { PreviewCodePane } from "@/components/gravitre/assistant/preview-code-pane"
import { PreActionCard } from "@/components/gravitre/pre-action-card"
import { preActionFromPendingTask } from "@/lib/pre-action-card"

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
    role?: string | null
    byteSize?: number | null
    durable?: boolean | null
    previewHtml?: string | null
    code?: string | null
    previewFormat?: string | null
    wordCount?: number | null
    rows?: Array<{ field?: string; value?: string; [key: string]: unknown }> | null
    plan_id?: string | null
    observation_ids?: string[] | null
    exportable?: boolean | null
    execution_path?: string | null
    recorded_at?: string | null
    outcome?: string | null
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
    hostedFiles?: Array<Record<string, unknown>> | null
    hosted_files?: Array<Record<string, unknown>> | null
    previewHtml?: string | null
    preview_html?: string | null
    code?: string | null
    content?: string | null
    previewFormat?: string | null
    format?: string | null
    title?: string | null
    rows?: Array<{ field?: string; value?: string; [key: string]: unknown }> | null
    plan_id?: string | null
    observation_ids?: string[] | null
    exportable?: boolean | null
    execution_path?: string | null
    recorded_at?: string | null
    kind?: string | null
    visits?: Array<{
      url?: string
      title?: string
      action?: string
      screenshot_digest?: string | null
      [key: string]: unknown
    }> | null
    screenshot_digest?: string | null
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

export function resolveBusinessOutcome(executionResult: ChatExecutionResult): BusinessOutcomeDto | null {
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
    integration?: string
    requires_approval?: boolean
    approval_reason?: string
    estimated_impact?: string
    risk_level?: string
    approval_id?: string
    conversation_id?: string
  }
  current_step?: OrchestrationStepPreview
}

type ChatExecutionPanelProps = {
  dialogueMode?: string | null
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  confirming?: boolean
  onConfirm?: () => void
  onReject?: () => void
  onModify?: () => void
  /** Admin/owner (or policy approver) — show Approve button; others see queued copy. */
  canApprove?: boolean
  /** The assistant's own answer text, so the panel never repeats it. */
  answerText?: string | null
  className?: string
}

function normalizeForCompare(text: string | null | undefined): string {
  return String(text || "")
    .toLowerCase()
    .replace(/[*_`#>]/g, "")
    .replace(/\s+/g, " ")
    .trim()
}

/** True when `candidate` adds nothing the reader has not already seen in `answer`. */
export function repeatsAnswer(candidate: string | null | undefined, answer: string | null | undefined): boolean {
  const c = normalizeForCompare(candidate)
  if (!c) return true
  const a = normalizeForCompare(answer)
  return Boolean(a) && a.includes(c)
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
    return `${total} steps across your connected apps. Reads run on their own; writes wait for you unless policy allows them.`
  }
  if (pendingTask.type === "connector_action") {
    const params = pendingTask.params
    const kind = params && typeof params.kind === "string" ? params.kind : "write"
    const where = params?.integration ? ` in ${params.integration.charAt(0).toUpperCase()}${params.integration.slice(1)}` : ""
    return kind === "read"
      ? `Reads data${where}. Nothing is changed.`
      : `Makes one change${where}. It runs only after you approve.`
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

type StepTone = "read" | "write" | "skipped"

const STEP_TAG: Record<StepTone, { label: string; className: string }> = {
  read: { label: "Runs automatically", className: "text-muted-foreground" },
  write: { label: "Needs approval", className: "text-[color:var(--warning)]" },
  skipped: { label: "Skipped", className: "text-muted-foreground" },
}

function StepBadge({ label, tone }: { label: string; tone: StepTone }) {
  return <span className={cn("shrink-0 text-xs font-medium", STEP_TAG[tone].className)}>{label}</span>
}

function stepTone(step: OrchestrationStepPreview): StepTone {
  if (step.supported === false) return "skipped"
  return step.kind === "read" ? "read" : "write"
}

function OrchestrationStepList({ steps }: { steps: OrchestrationStepPreview[] }) {
  if (!steps.length) return null
  const tones = steps.map(stepTone)
  const count = (tone: StepTone) => tones.filter((t) => t === tone).length
  const tally = [
    count("read") ? `${count("read")} automatic` : null,
    count("write") ? `${count("write")} need${count("write") === 1 ? "s" : ""} approval` : null,
    count("skipped") ? `${count("skipped")} skipped` : null,
  ].filter(Boolean)
  return (
    <div className="mt-3 flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{tally.join(" · ")}</p>
      <ol className="flex flex-col">
        {steps.map((step, index) => {
          const tone = tones[index]
          const last = index === steps.length - 1
          return (
            <li key={step.step_id || index} className="relative flex gap-3 pb-3 last:pb-0">
              {!last ? (
                <span aria-hidden className="absolute left-[9px] top-6 bottom-0 w-px bg-border" />
              ) : null}
              <span
                aria-hidden
                className={cn(
                  "relative mt-0.5 flex h-[19px] w-[19px] shrink-0 items-center justify-center rounded-full border text-[10px] font-medium tabular-nums",
                  tone === "write"
                    ? "border-[color:var(--warning)]/50 text-[color:var(--warning)]"
                    : "border-border text-muted-foreground",
                )}
              >
                {index + 1}
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span
                    className={cn(
                      "min-w-0 text-sm text-foreground",
                      tone === "skipped" && "text-muted-foreground line-through decoration-border",
                    )}
                  >
                    {step.label || "Step"}
                  </span>
                  <StepBadge label={STEP_TAG[tone].label} tone={tone} />
                </div>
                {step.skip_reason ? (
                  <p className="text-xs text-muted-foreground">{step.skip_reason}</p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
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

function artifactHref(artifact: ChatArtifact): string | null {
  return artifact.result_url || artifact.resultUrl || null
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

export function canonicalArtifactRows(
  executionResult: ChatExecutionResult,
): Array<Record<string, string>> {
  const fromArtifacts = executionResult.artifacts?.flatMap((artifact) => {
    const nested = artifact.metadata?.rows
    return Array.isArray(nested) ? nested : []
  })
  const visitSource = executionResult.structured?.visits
  const fromVisits = Array.isArray(visitSource)
    ? visitSource.map((visit, index) => ({
        step: String(index + 1),
        title: String(visit.title || ""),
        url: String(visit.url || ""),
        action: String(visit.action || ""),
      }))
    : []
  const raw = executionResult.structured?.rows?.length
    ? executionResult.structured.rows
    : fromArtifacts?.length
      ? fromArtifacts
      : fromVisits
  if (!Array.isArray(raw)) return []
  return raw
    .map((row) => {
      if (!row || typeof row !== "object") return null
      const out: Record<string, string> = {}
      for (const [key, value] of Object.entries(row)) {
        if (value === null || value === undefined) continue
        if (typeof value === "object") continue
        out[key] = String(value)
      }
      return Object.keys(out).length ? out : null
    })
    .filter((row): row is Record<string, string> => row !== null)
}

type CanonicalProvenanceProps = {
  planId?: string | null
  observationIds?: string[] | null
  exportable?: boolean | null
  screenshotDigest?: string | null
  executionPath?: string | null
}

/** Plan, observation and execution ids: audit detail, never the main answer. */
export function CanonicalProvenance({
  planId,
  observationIds,
  exportable,
  screenshotDigest,
  executionPath,
}: CanonicalProvenanceProps) {
  const digest = (screenshotDigest || "").trim()
  return (
    <>
      <p className="mt-2 text-[11px] text-muted-foreground">
        {planId ? `Plan ${planId}` : "Bound to the current plan"}
        {observationIds?.length ? ` · Observation ${observationIds[0]}` : ""}
        {exportable ? " · Exportable from conversation state" : ""}
        {executionPath ? (
          <>
            {" · "}
            <span data-testid="canonical-execution-path">{executionPath}</span>
          </>
        ) : null}
      </p>
      {digest ? (
        <p className="mt-1 text-[11px] text-muted-foreground" data-testid="canonical-screenshot-digest">
          Browser screenshot digest {digest.slice(0, 16)}…
        </p>
      ) : null}
    </>
  )
}

export function CanonicalArtifactTable({
  rows,
  provenance = true,
  ...provenanceProps
}: CanonicalProvenanceProps & {
  rows: Array<Record<string, string>>
  /** False when the ids are shown elsewhere (the chat Details disclosure). */
  provenance?: boolean
}) {
  if (!rows.length) return null
  const columns = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row))),
  ).filter((key) => key !== "password")
  return (
    <div className="mt-3 overflow-x-auto" data-testid="canonical-artifact-table">
      <table className="w-full min-w-[16rem] border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-border/70 text-muted-foreground">
            {columns.map((column) => (
              <th key={column} className="py-1 pr-3 font-medium">
                {column.charAt(0).toUpperCase() + column.slice(1).replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.field || row.system || row.object || row.action || index}`} className="border-b border-border/40">
              {columns.map((column) => (
                <td key={column} className="py-1 pr-3 text-foreground">
                  {row[column] || ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {provenance ? <CanonicalProvenance {...provenanceProps} /> : null}
    </div>
  )
}

function ArtifactCards({ artifacts }: { artifacts: ChatArtifact[] }) {
  if (!artifacts.length) return null
  const hosted = artifacts.filter((a) => a.kind === "hosted_file")
  const other = artifacts.filter((a) => a.kind !== "hosted_file")
  return (
    <div className="mt-3 flex flex-col gap-1">
      <p className="text-xs font-medium text-muted-foreground">
        {artifacts.length === 1 ? "1 artifact" : `${artifacts.length} artifacts`}
      </p>
      <div className="divide-y divide-border/60 rounded-[var(--np-radius-md)] border border-border/60 px-3">
        {hosted.slice(0, 8).map((artifact) => (
          <div key={artifact.artifact_id || artifact.artifactId || artifact.title} className="py-1.5">
            <FileReferenceChip file={artifact} />
          </div>
        ))}
        {other.slice(0, 6).map((artifact) => {
          const href = artifactHref(artifact)
          const title = artifact.title || artifact.kind || "Artifact"
          const preview = artifact.preview?.trim()
          const external = href ? isExternalUrl(href) : false
          const key = artifact.artifact_id || artifact.artifactId || title
          const rowClass =
            "flex w-full items-baseline justify-between gap-3 py-1.5 text-left text-xs text-foreground"
          const inner = (
            <>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate">
                  {title}
                  {artifact.kind ? (
                    <span className="ml-2 font-mono text-[11px] text-muted-foreground">{artifact.kind}</span>
                  ) : null}
                </span>
                {preview ? <span className="line-clamp-1 text-muted-foreground">{preview}</span> : null}
              </span>
            </>
          )
          if (!href) {
            return (
              <div key={key} className={rowClass}>
                {inner}
              </div>
            )
          }
          return external ? (
            <a
              key={key}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open artifact"
              className={cn(rowClass, "hover:underline")}
            >
              {inner}
            </a>
          ) : (
            <Link key={key} href={href} aria-label="Open artifact" className={cn(rowClass, "hover:underline")}>
              {inner}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export function ChatExecutionPanel({
  dialogueMode,
  executionResult,
  pendingTask,
  confirming = false,
  onConfirm,
  onReject,
  onModify,
  canApprove = false,
  answerText,
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
            ? "border-warning/25 bg-warning/5"
            : "border-destructive/25 bg-destructive/5",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <ShieldAlert
            className={cn(
              "mt-0.5 h-4 w-4 shrink-0",
              unverifiable ? "text-warning-text" : "text-danger-text",
            )}
          />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-foreground">
              {executionResult.task_label || executionResult.title || "Action did not complete"}
            </p>
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
    const structured = executionResult.structured || {}
    const fromStructured = hostedFilesFromUnknown(structured)
    const previewHtml =
      structured.previewHtml ||
      structured.preview_html ||
      artifacts.find((a) => a.metadata?.previewHtml)?.metadata?.previewHtml ||
      null
    const code =
      structured.code ||
      structured.content ||
      artifacts.find((a) => a.metadata?.code)?.metadata?.code ||
      null
    const previewFormat =
      structured.previewFormat ||
      structured.format ||
      artifacts.find((a) => a.metadata?.previewFormat)?.metadata?.previewFormat ||
      null
    // A report Gravitre bound from its own observations restates the answer; it is
    // supporting detail. A generated document or page is the deliverable itself.
    const boundReport =
      artifacts.some((a) => a.source === "e5_execution_plan") ||
      Boolean(structured.plan_id && (structured as { outcome?: string | null }).outcome)
    const deliverableInline = !boundReport && Boolean(previewHtml || (code && String(code).trim()))
    const body = executionResult.body?.trim() || ""
    const showBody = Boolean(body) && !repeatsAnswer(body, answerText)
    const showWhatThisMeans =
      Boolean(whatThisMeans) && !repeatsAnswer(whatThisMeans, answerText) && whatThisMeans !== body
    const showHeading = isPreview || deliverableInline
    const tableRows = canonicalArtifactRows(executionResult)
    // One row restates the answer ("57 contacts"); several rows are content.
    const tableInline = tableRows.length > 1
    const hostedArtifacts = artifacts.filter((a) => a.kind === "hosted_file")
    const otherArtifacts = artifacts.filter((a) => a.kind !== "hosted_file")
    const provenance = {
      planId: structured.plan_id || executionResult.entity_id,
      observationIds: structured.observation_ids,
      exportable: structured.exportable,
      screenshotDigest: structured.screenshot_digest,
      executionPath: structured.execution_path,
    }
    const hasProvenance = Boolean(
      tableRows.length ||
        structured.plan_id ||
        structured.observation_ids?.length ||
        structured.execution_path ||
        structured.screenshot_digest,
    )
    const hasDetails =
      hasProvenance ||
      steps.length > 1 ||
      otherArtifacts.length > 0 ||
      (!deliverableInline && Boolean(previewHtml || code))
    const external = resolveExternalUrl(executionResult)
    const vendor = (executionResult.integration || "source").trim()
    const externalLabel = vendor
      ? `Open in ${vendor.charAt(0).toUpperCase()}${vendor.slice(1)}`
      : "Open in source"
    return (
      <div className={cn("mt-3 text-sm", className)} data-testid="execution-result-summary">
        {showHeading ? (
          <p className="flex items-center gap-2 text-[15px] font-medium leading-snug text-foreground">
            <CheckCircle2 className={cn("h-4 w-4 shrink-0", HIGHLIGHT.brand)} aria-hidden />
            {isPreview
              ? "Live vendor preview"
              : executionResult.task_label || executionResult.title || "Task completed"}
          </p>
        ) : null}
        {showBody ? (
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground">{body}</p>
        ) : null}
        {showWhatThisMeans ? (
          <p className="mt-2 text-sm leading-relaxed text-foreground">{whatThisMeans}</p>
        ) : null}
        {recommendation?.title ? (
          <p className="mt-2 text-sm leading-relaxed text-foreground" data-testid="execution-next-step">
            <span className="font-medium">Next step: </span>
            {recommendation.title}
            {recommendation.reason ? `. ${recommendation.reason}` : ""}
            {recommendation.suggestedUtterance ? (
              <span className="text-muted-foreground">
                {" "}Say &ldquo;{recommendation.suggestedUtterance}&rdquo; and I&apos;ll do it.
              </span>
            ) : null}
          </p>
        ) : null}
        {assumptions.length > 0 ? (
          <div className="mt-2 rounded-lg border border-warning/20 bg-warning/5 px-2.5 py-2 text-xs text-warning-text">
            <p className="font-medium">I assumed</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {assumptions.slice(0, 4).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {tableInline ? <CanonicalArtifactTable rows={tableRows} provenance={false} /> : null}
        {fromStructured.length && !hostedArtifacts.length ? (
          <FileReferenceChipRow files={fromStructured} />
        ) : null}
        <ArtifactCards artifacts={hostedArtifacts} />
        {deliverableInline ? (
          <PreviewCodePane
            title={structured.title || executionResult.title || "Output"}
            code={code}
            previewHtml={previewHtml}
            previewFormat={previewFormat}
          />
        ) : null}
        {resultUrl || external ? (
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
            {external ? (
              <Button asChild size="sm" variant="outline" className="h-8">
                <a href={external} target="_blank" rel="noopener noreferrer">
                  {externalLabel}
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </a>
              </Button>
            ) : null}
          </div>
        ) : null}
        {hasDetails ? (
          <details className="group/details mt-3 text-xs text-muted-foreground" data-testid="execution-details">
            <summary className="cursor-pointer select-none text-foreground/80">Details</summary>
            <div className="mt-2 border-l-2 border-border/60 pl-3">
              {tableInline ? (
                hasProvenance ? <CanonicalProvenance {...provenance} /> : null
              ) : (
                <CanonicalArtifactTable rows={tableRows} {...provenance} />
              )}
              {steps.length > 1 ? (
                <div className="mt-3 flex flex-col gap-1.5">
                  <p className="text-xs font-medium text-muted-foreground">
                    {steps.length} steps
                  </p>
                  <ol className="flex flex-col gap-1.5">
                    {steps.map((step) => (
                      <li key={step.stepId || step.index} className="flex items-baseline gap-2 text-sm">
                        {step.success === false ? (
                          <span aria-label="Not completed" className="h-3 w-3 shrink-0 translate-y-0.5 rounded-full border border-border" />
                        ) : (
                          <CheckCircle2 aria-label="Completed" className="h-3.5 w-3.5 shrink-0 translate-y-0.5 text-muted-foreground" />
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="text-foreground">{step.label || "Step"}</span>
                          {step.summary ? (
                            <span className="text-muted-foreground"> · {step.summary}</span>
                          ) : null}
                          {step.evidenceUrl ? (
                            <span className="block truncate text-xs text-muted-foreground">{step.evidenceUrl}</span>
                          ) : null}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
              {!deliverableInline ? (
                <PreviewCodePane
                  title={structured.title || executionResult.title || "Output"}
                  code={code}
                  previewHtml={previewHtml}
                  previewFormat={previewFormat}
                />
              ) : null}
              <ArtifactCards artifacts={otherArtifacts} />
            </div>
          </details>
        ) : null}
      </div>
    )
  }

  if (
    (dialogueMode === "confirm" || dialogueMode === "awaiting_approval") &&
    pendingTask?.type
  ) {
    const isConnector = pendingTask.type === "connector_action"
    const isOrchestration = pendingTask.type === "connector_orchestration"
    // Trust server dialogue_mode: "confirm" means this user may approve (HITL roles/users).
    // "awaiting_approval" means the request was queued for configured approvers.
    const queuedForApprover =
      dialogueMode === "awaiting_approval" ||
      pendingTask.status === "awaiting_admin_approval" ||
      (dialogueMode === "confirm" && !canApprove && pendingTask.status !== "awaiting_confirm")

    if (isConnector) {
      const payload = preActionFromPendingTask(pendingTask, {
        description: queuedForApprover
          ? "Your request will be sent for approval."
          : pendingDescription(pendingTask),
      })
      if (payload) {
        return (
          <div className={cn("mt-3", className)}>
            <PreActionCard
              payload={payload}
              variant="chat"
              confirming={Boolean(confirming)}
              approveLabel={confirmButtonLabel(pendingTask, Boolean(confirming))}
              onApprove={queuedForApprover ? undefined : onConfirm}
              onReject={queuedForApprover ? undefined : onReject}
              onModify={queuedForApprover ? undefined : onModify}
              hideActions={queuedForApprover}
              footer={
                queuedForApprover ? (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="flex items-center gap-2 text-sm text-foreground">
                      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[color:var(--warning)]" />
                      Waiting on an approver
                    </p>
                    {pendingTask.params?.approval_id ? (
                      <Button asChild size="sm" variant="outline" className="h-8">
                        <Link href={`/approvals?id=${encodeURIComponent(String(pendingTask.params.approval_id))}`}>
                          Open in Approvals
                          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                ) : undefined
              }
            />
          </div>
        )
      }
    }

    return (
      <div className={cn("mt-3", className)}>
        <PlanApprovalChrome
          title={
            queuedForApprover
              ? "Pending approval"
              : isOrchestration
                ? pendingTask.status === "awaiting_step_confirm"
                  ? "Step approval required"
                  : "Orchestration plan"
                : isConnector
                  ? "Approval required"
                  : "Ready to execute"
          }
        >
          {(isConnector || pendingTask.status === "awaiting_step_confirm") && (
            <p className="text-sm font-medium text-foreground">{pendingLabel(pendingTask)}</p>
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
        </PlanApprovalChrome>
      </div>
    )
  }

  return null
}
