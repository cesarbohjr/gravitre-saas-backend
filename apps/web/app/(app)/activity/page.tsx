"use client"

/**
 * Activity hub: BusinessOutcome list, WorkObjects and Failure Alerts, laid out to
 * the "Gravitre Agents v4" design (hero, segmented views, Outcomes inspector).
 *
 * The inspector shows the run trace, a suggested next step, summary and
 * verification, then evidence / explanation / execution proof / diff / undo.
 * Every value comes from the BusinessOutcome DTO; nothing is invented.
 */

import { Suspense, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { ArrowLeft, ChevronRight, Download, ExternalLink, Sparkles, X } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { OvPager } from "@/components/workspace/ov-pager"
import type { BusinessOutcomeDto } from "@/components/gravitre/business-outcome/business-outcome-view"
import { buildActivityTraceStages, type ActivityTraceStage } from "@/components/activity/activity-trace-panel"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { FailureAlertsPanel } from "@/components/workflows/failure-alerts-panel"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { useGravitreAIWorkspace, usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { summarizeActivityView } from "@/lib/activity-view-summary"
import { auditApi, businessOutcomesApi, runsApi, workObjectsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { resolveProvider } from "@/lib/provider-registry"
import { useIsMobile } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"
import "@/components/workspace/ops-v4.css"

type ActivityTab = "all" | "objects" | "failures"

type WorkObjectDto = {
  id: string
  objectType?: string
  department?: string
  title?: string
  objective?: string | null
  owner?: string | null
  status?: string
  priority?: string
  externalEntityType?: string | null
  externalEntityId?: string | null
  systemsInvolved?: string[]
  agentsInvolved?: string[]
  businessOutcomeRefs?: string[]
  outcome?: Record<string, unknown> | null
  roi?: Record<string, unknown> | null
  createdAt?: string | null
  lastActivityAt?: string | null
}

type WorkObjectEventDto = {
  id: string
  eventType?: string
  actionName?: string | null
  actionStatus?: string | null
  systemName?: string | null
  runId?: string | null
  businessOutcomeId?: string | null
  createdAt?: string | null
}

const STATUS_OPTIONS = [
  ["all", "All"],
  ["failed", "Failed"],
  ["completed", "Completed"],
  ["running", "Running"],
  ["partial_success", "Partial success"],
  ["flagged_for_review", "Flagged for review"],
] as const

const LIFECYCLE_OPTIONS = [
  ["all", "All"],
  ["presented", "Presented"],
  ["verified", "Verified"],
  ["created", "Created"],
  ["approved", "Approved"],
  ["undone", "Undone"],
] as const

const OBJECT_TYPES = [
  ["all", "All types"], ["opportunity", "Opportunity"], ["campaign", "Campaign"], ["candidate", "Candidate"],
  ["financial_issue", "Financial issue"], ["ticket", "Ticket"], ["contract_matter", "Contract / matter"],
  ["incident", "Incident"], ["vulnerability", "Vulnerability"], ["vendor", "Vendor"], ["feature", "Feature"],
  ["issue_pr", "Issue / PR"], ["objective", "Objective"],
] as const
const OBJECT_DEPARTMENTS = [
  ["all", "All departments"], ["sales", "Sales"], ["marketing", "Marketing"], ["hr", "HR"], ["finance", "Finance"],
  ["support", "Support"], ["legal", "Legal"], ["security", "Security"], ["procurement", "Procurement"],
  ["engineering", "Engineering"], ["operations", "Operations"],
] as const
const OBJECT_STATUSES = [
  ["all", "All statuses"], ["identified", "Identified"], ["planned", "Planned"], ["in_progress", "In progress"],
  ["awaiting_approval", "Awaiting approval"], ["blocked", "Blocked"], ["completed", "Completed"], ["failed", "Failed"],
] as const
const OBJECT_PRIORITIES = [
  ["all", "All priorities"], ["low", "Low"], ["medium", "Medium"], ["high", "High"], ["critical", "Critical"],
] as const

function asOutcome(raw: Record<string, unknown>): BusinessOutcomeDto {
  return raw as unknown as BusinessOutcomeDto
}

function humanize(value: string | null | undefined): string {
  const text = String(value ?? "").replace(/[_-]+/g, " ").trim()
  if (!text) return ""
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase()
}

function statusTone(status: string | null | undefined): "green" | "red" | "amber" | undefined {
  const s = String(status ?? "").toLowerCase()
  if (!s) return undefined
  if (s.includes("fail") || s.includes("error") || s.includes("reject") || s === "blocked") return "red"
  if (s.includes("flag") || s.includes("partial") || s.includes("approval") || s.includes("pending") || s.includes("running") || s === "in_progress")
    return "amber"
  if (s.includes("complete") || s.includes("success") || s.includes("verified") || s === "approved") return "green"
  return undefined
}

function isException(outcome: BusinessOutcomeDto): boolean {
  const tone = statusTone(outcome.status)
  return tone === "red" || String(outcome.status ?? "").toLowerCase() === "flagged_for_review"
}

function appName(slug: string | null | undefined): string {
  if (!slug) return ""
  return resolveProvider(slug)?.name ?? humanize(slug)
}

function updatedLabel(at: number | null, now: number): string {
  if (at == null) return "Not updated yet"
  const secs = Math.max(0, Math.floor((now - at) / 1000))
  if (secs < 45) return "Updated just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `Updated ${Math.max(1, mins)} min ago`
  return `Updated ${Math.floor(mins / 60)} h ago`
}

/** The design's four-beat trace: the outcome itself is the page title, and an unproven check reads as "not confirmed", not as a second failure. */
function traceStages(outcome: BusinessOutcomeDto): ActivityTraceStage[] {
  return buildActivityTraceStages(outcome)
    .filter((stage) => stage.id !== "outcome")
    .map((stage) =>
      stage.id === "verification" && stage.status !== "completed"
        ? { ...stage, label: "Verify", status: "pending", summary: "Could not confirm" }
        : stage.id === "verification"
          ? { ...stage, label: "Verify" }
          : stage,
    )
}

function stageDot(stage: ActivityTraceStage): "ok" | "fail" | "run" | "" {
  if (stage.status === "completed") return "ok"
  if (stage.status === "failed") return "fail"
  if (stage.status === "running" || stage.status === "awaiting_approval") return "run"
  return ""
}

function stageLabel(stage: ActivityTraceStage): string {
  return stage.label === stage.label.toUpperCase() ? humanize(stage.label) : stage.label
}

type Verdict = { tone: "green" | "red" | "amber"; label: string; code: string | null }

function verdictOf(outcome: BusinessOutcomeDto): Verdict {
  const v = outcome.sections?.verification
  const code = v?.checkFailed || v?.method || null
  if (v?.verified === true || (v?.verified == null && v?.confidence === "verified")) return { tone: "green", label: "Verified", code }
  if (v?.confidence === "accepted_unproven") return { tone: "amber", label: "Accepted, not yet proven", code }
  return { tone: "red", label: "Not verified", code }
}

type NextStep = {
  text: string
  fix: { label: string; href?: string; prompt?: string } | null
}

/** The suggested next step only uses what the outcome reports: next actions, the finding, or a recommendation. */
function nextStepOf(outcome: BusinessOutcomeDto): NextStep | null {
  const s = outcome.sections
  const recommendation = (s?.recommendations ?? []).find((r) => r?.title || r?.reason)
  const text =
    s?.verification?.nextActions?.find((a) => a && a.trim()) ||
    recommendation?.reason ||
    recommendation?.title ||
    (isException(outcome) ? s?.verification?.finding : null) ||
    null
  if (!text) return null
  const integration = s?.evidence?.integration
  const external = (s?.evidence?.links ?? []).find((l) => l?.href && /^https?:/i.test(l.href))
  if (external && integration) return { text, fix: { label: `Check in ${appName(integration)}`, href: external.href } }
  if (recommendation?.href) return { text, fix: { label: recommendation.title || "Open", href: recommendation.href } }
  if (recommendation?.suggestedUtterance) {
    return { text, fix: { label: recommendation.title || "Ask Gravitre to do it", prompt: recommendation.suggestedUtterance } }
  }
  if (external) return { text, fix: { label: external.label || "Open evidence", href: external.href } }
  return { text, fix: null }
}

function proofFields(outcome: BusinessOutcomeDto): Array<[string, string]> {
  const args = outcome.sections?.metadata?.actionArgs ?? outcome.sections?.metadata?.action_args
  if (!args || typeof args !== "object") return []
  return Object.entries(args as Record<string, unknown>).map(([k, v]) => [
    k,
    typeof v === "string" ? v : JSON.stringify(v),
  ])
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (next: string) => void
  options: ReadonlyArray<readonly [string, string]>
}) {
  return (
    <label className="ov-field">
      <span>{label}</span>
      <select className="ov-select" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  )
}

function OutcomeDetail({
  outcome,
  onRetry,
  retrying,
  onAsk,
  pager,
}: {
  outcome: BusinessOutcomeDto
  onRetry: () => void
  retrying: boolean
  onAsk: (prompt: string) => void
  pager?: ReactNode
}) {
  const s = outcome.sections
  const stages = traceStages(outcome)
  const verdict = verdictOf(outcome)
  const step = nextStepOf(outcome)
  const fields = proofFields(outcome)
  const links = s?.evidence?.links ?? []
  const tone = statusTone(outcome.status || outcome.lifecycleState)
  const kicker = [humanize(outcome.kind), (outcome.lifecycleState ?? "").toLowerCase()].filter(Boolean).join(" · ")

  return (
    <>
      <div className="ov-detail-top start">
        <div className="ov-col">
          {kicker ? <span className="ov-kicker">{kicker}</span> : null}
          <h3>{outcome.title || "Untitled outcome"}</h3>
        </div>
        <span className="ov-top-right">
          {outcome.status ? (
            <span className={cn("ov-pill", tone)}>
              <span className="ov-dot" aria-hidden />
              {humanize(outcome.status)}
            </span>
          ) : null}
          {pager}
        </span>
      </div>

      {stages.length > 0 ? (
        <div className="ov-trace">
          <b>Run trace</b>
          <ol>
            {stages.map((stage) => {
              const dot = stageDot(stage)
              return (
                <li key={stage.id}>
                  <span className="mk">
                    <span className={cn("dot", dot)} aria-hidden>
                      {dot === "ok" ? "✓" : dot === "fail" ? "!" : ""}
                    </span>
                    <span className={cn("ln", dot === "ok" && "ok")} aria-hidden />
                  </span>
                  <b>{stageLabel(stage)}</b>
                  <span>
                    <span className="ov-sr">{humanize(stage.status)}. </span>
                    {stage.summary || humanize(stage.status)}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
      ) : null}

      {step ? (
        <div className="ov-suggest">
          <span className="ic" aria-hidden>
            <Sparkles size={16} />
          </span>
          <div className="bd">
            <b>Suggested next step</b>
            <p>{step.text}</p>
            <div className="ov-actions">
              {step.fix?.href ? (
                /^https?:/i.test(step.fix.href) ? (
                  <a className="ov-btn dark sm" href={step.fix.href} target="_blank" rel="noreferrer">
                    {step.fix.label}
                  </a>
                ) : (
                  <Link className="ov-btn dark sm" href={step.fix.href}>
                    {step.fix.label}
                  </Link>
                )
              ) : step.fix?.prompt ? (
                <button type="button" className="ov-btn dark sm" onClick={() => onAsk(step.fix!.prompt!)}>
                  {step.fix.label}
                </button>
              ) : null}
              {isException(outcome) ? (
                <button type="button" className="ov-btn sm" onClick={onRetry} disabled={retrying}>
                  {retrying ? "Retrying..." : "Retry safely"}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <div className="ov-cards2">
        <div className="ov-card2">
          <b>Summary</b>
          <p>{s?.summary || "No summary reported."}</p>
        </div>
        <div className="ov-card2">
          <b>Verification</b>
          <span className={cn("ov-verdict", verdict.tone)}>
            <span className="ov-dot" aria-hidden />
            {verdict.label}
          </span>
          {verdict.code ? <span className="code">{verdict.code}</span> : null}
        </div>
      </div>

      <div className="ov-acc">
        <details>
          <summary>
            <ChevronRight size={16} aria-hidden />
            <span className="l">Evidence</span>
            <span className="m">View in Gravitre</span>
          </summary>
          <div className="body">
            {links.length === 0 && !s?.evidence?.entityId ? <p>No evidence links reported.</p> : null}
            {s?.evidence?.entityId ? (
              <p>
                {humanize(s.evidence.entityType) || "Record"} {s.evidence.entityId}
                {s.evidence.integration ? ` in ${appName(s.evidence.integration)}` : ""}
              </p>
            ) : null}
            <div className="links">
              {links.map((link) =>
                /^https?:/i.test(link.href) ? (
                  <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
                    {link.label || link.href}
                  </a>
                ) : (
                  <Link key={link.href} href={link.href}>
                    {link.label || link.href}
                  </Link>
                ),
              )}
              {outcome.runId ? <Link href={`/runs/${outcome.runId}?trace=1`}>View in Gravitre</Link> : null}
            </div>
          </div>
        </details>
        <details>
          <summary>
            <ChevronRight size={16} aria-hidden />
            <span className="l">Explanation</span>
            <span className="m">Why the agent did this</span>
          </summary>
          <div className="body">
            <p>{s?.explanation || s?.verification?.detail || "No explanation recorded for this outcome."}</p>
          </div>
        </details>
        <details>
          <summary>
            <ChevronRight size={16} aria-hidden />
            <span className="l">Execution proof</span>
            <span className="m">
              {fields.length} field{fields.length === 1 ? "" : "s"}
            </span>
          </summary>
          <div className="body">
            {fields.length === 0 ? (
              <p>No action arguments were recorded.</p>
            ) : (
              <dl>
                {fields.map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </details>
        <details>
          <summary>
            <ChevronRight size={16} aria-hidden />
            <span className="l">Diff</span>
            <span className="m">What changed</span>
          </summary>
          <div className="body">
            {s?.diff?.available && s.diff.prior ? (
              <>
                <p>Before this action:</p>
                <pre>{JSON.stringify(s.diff.prior, null, 2)}</pre>
              </>
            ) : null}
            <p>{s?.diff?.note || (s?.diff?.available ? "" : "No before-and-after was captured for this action.")}</p>
          </div>
        </details>
        <details>
          <summary>
            <ChevronRight size={16} aria-hidden />
            <span className="l">Undo</span>
            <span className="m">{s?.undo?.available ? "Available" : "Nothing to undo"}</span>
          </summary>
          <div className="body">
            {s?.undo?.available ? (
              <>
                <p>{s.undo.compensatingAction ? `Undo runs ${s.undo.compensatingAction}.` : "This action can be undone."}</p>
                <button
                  type="button"
                  className="ov-btn sm"
                  onClick={() => onAsk(`Undo this outcome: ${outcome.title ?? "the selected action"}. Confirm with me before running it.`)}
                >
                  Ask Gravitre to undo
                </button>
              </>
            ) : (
              <p>{s?.undo?.honestUnavailableReason || "There is nothing to undo for this outcome."}</p>
            )}
          </div>
        </details>
      </div>

      <div className="ov-foot start">
        {outcome.runId ? (
          <Link className="ov-btn dark" href={`/runs/${outcome.runId}?trace=1`}>
            View the run
          </Link>
        ) : null}
        <AskGravitreSummonButton
          className="ov-btn"
          label="Ask Gravitre about this"
          prompt="Explain this outcome's reported state, evidence and next action. Do not assume completion means verification."
        />
      </div>
    </>
  )
}

function WorkObjectDetail({
  workObject,
  events,
  loading,
  pager,
}: {
  workObject: WorkObjectDto
  events: WorkObjectEventDto[]
  loading: boolean
  pager?: ReactNode
}) {
  const tone = statusTone(workObject.status)
  return (
    <>
      <div className="ov-detail-top start">
        <div className="ov-col">
          <span className="ov-kicker">
            {[humanize(workObject.objectType) || "Objective", humanize(workObject.department)].filter(Boolean).join(" · ")}
          </span>
          <h3>{workObject.title || "Untitled work object"}</h3>
        </div>
        <span className="ov-top-right">
          <span className={cn("ov-pill", tone)}>
            <span className="ov-dot" aria-hidden />
            {humanize(workObject.status || "identified")}
          </span>
          {pager}
        </span>
      </div>
      <p className="desc">{workObject.objective || "No objective recorded yet."}</p>
      <div className="ov-wo-grid">
        <span>
          <strong>Owner:</strong> {workObject.owner || "Unassigned"}
        </span>
        <span>
          <strong>Priority:</strong> {humanize(workObject.priority) || "Not set"}
        </span>
        <span>
          <strong>Systems:</strong> {(workObject.systemsInvolved || []).map(appName).join(", ") || "None"}
        </span>
        <span>
          <strong>Agents:</strong> {(workObject.agentsInvolved || []).join(", ") || "None"}
        </span>
      </div>
      <div className="ov-card2">
        <b>Lifecycle timeline</b>
        {loading ? (
          <p>Loading...</p>
        ) : events.length === 0 ? (
          <p>No attributed actions yet.</p>
        ) : (
          <ul className="ov-events">
            {events.map((event) => (
              <li key={event.id}>
                <span className="row">
                  <b>{event.actionName || humanize(event.eventType) || "Action"}</b>
                  <span className={cn("ov-status", statusTone(event.actionStatus || "completed"))}>
                    <i aria-hidden />
                    {humanize(event.actionStatus || "completed")}
                  </span>
                </span>
                <span>
                  {event.systemName ? `${appName(event.systemName)} · ` : ""}
                  {event.createdAt ? new Date(event.createdAt).toLocaleString() : "Time not recorded"}
                </span>
                {event.runId ? (
                  <Link href={`/runs/${event.runId}`}>
                    Open run <ExternalLink size={12} aria-hidden />
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

function ActivityPageInner() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { summonWorkspace } = useGravitreAIWorkspace()
  const compact = useIsMobile(1024)
  const tabParam = searchParams.get("tab")
  const tab: ActivityTab = tabParam === "failures" ? "failures" : tabParam === "objects" ? "objects" : "all"

  const [status, setStatus] = useState<string>("all")
  const [lifecycle, setLifecycle] = useState<string>("all")
  const [integration, setIntegration] = useState("")
  const [objectType, setObjectType] = useState<string>("all")
  const [objectDepartment, setObjectDepartment] = useState<string>("all")
  const [objectStatus, setObjectStatus] = useState<string>("all")
  const [objectPriority, setObjectPriority] = useState<string>("all")
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(null)
  const [selectedWorkObjectId, setSelectedWorkObjectId] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const setTab = (next: ActivityTab) => {
    const params = new URLSearchParams(searchParams.toString())
    if (next === "all") params.delete("tab")
    else params.set("tab", next)
    const qs = params.toString()
    setSelectedOutcomeId(null)
    setSelectedWorkObjectId(null)
    router.replace(qs ? `/activity?${qs}` : "/activity")
  }

  const listKey = user ? ["business-outcomes", status, lifecycle, integration.trim().toLowerCase()] : null
  const { data, error, isLoading, mutate, isValidating } = useSWR(
    listKey,
    () =>
      businessOutcomesApi.list({
        status: status === "all" ? undefined : status,
        lifecycleState: lifecycle === "all" ? undefined : lifecycle,
        integration: integration.trim() || undefined,
        limit: 50,
      }),
    { revalidateOnFocus: true, onSuccess: () => setUpdatedAt(Date.now()) },
  )

  // Always loaded so the "Work objects" segment carries its real count.
  const workObjectListKey = user ? ["work-objects", objectType, objectDepartment, objectStatus, objectPriority] : null
  const {
    data: workObjectListData,
    error: workObjectListError,
    isLoading: workObjectsLoading,
    mutate: mutateWorkObjects,
  } = useSWR(
    workObjectListKey,
    () =>
      workObjectsApi.list({
        objectType: objectType === "all" ? undefined : objectType,
        department: objectDepartment === "all" ? undefined : objectDepartment,
        status: objectStatus === "all" ? undefined : objectStatus,
        priority: objectPriority === "all" ? undefined : objectPriority,
        limit: 80,
      }),
    { revalidateOnFocus: true },
  )

  const outcomes = useMemo(
    () => (data?.businessOutcomes ?? []).map((row) => asOutcome(row as Record<string, unknown>)),
    [data],
  )
  const workObjects = useMemo(
    () => (workObjectListData?.workObjects ?? []).map((row) => row as unknown as WorkObjectDto),
    [workObjectListData],
  )

  const outcomeKey = (outcome: BusinessOutcomeDto) => outcome.id || outcome.runId || ""

  const selectedOutcomeExplicit =
    selectedOutcomeId == null
      ? null
      : outcomes.find((o) => o.id === selectedOutcomeId) || outcomes.find((o) => o.runId === selectedOutcomeId) || null
  // Desktop opens on the top exception (else the newest row), as in the design. On phones the
  // list comes first and the inspector stays closed until then: a tap opens it full width.
  const topOutcome = compact ? null : outcomes.find(isException) || outcomes[0] || null
  const selectedOutcome = selectedOutcomeExplicit || topOutcome

  const selectedWorkObjectExplicit =
    selectedWorkObjectId == null ? null : workObjects.find((o) => o.id === selectedWorkObjectId) || null
  const selectedWorkObject = selectedWorkObjectExplicit || (compact ? null : workObjects[0] || null)

  const mobileDetailOpen = tab === "objects" ? selectedWorkObjectExplicit != null : selectedOutcomeExplicit != null

  const { data: workObjectDetailData, isLoading: workObjectDetailLoading } = useSWR(
    user && tab === "objects" && selectedWorkObject?.id ? ["work-object-detail", selectedWorkObject.id] : null,
    () => workObjectsApi.get(String(selectedWorkObject?.id || ""), 250),
    { revalidateOnFocus: true },
  )
  const workObjectEvents = useMemo(
    () => (workObjectDetailData?.events ?? []).map((row) => row as unknown as WorkObjectEventDto),
    [workObjectDetailData],
  )

  usePublishGravitreAISelection(
    tab === "objects"
      ? selectedWorkObject
        ? {
            kind: "work_object",
            id: selectedWorkObject.id,
            label: selectedWorkObject.title?.trim() || selectedWorkObject.objective?.trim() || selectedWorkObject.id,
          }
        : null
      : tab === "all" && selectedOutcome
        ? {
            kind: "outcome",
            id: selectedOutcome.id || selectedOutcome.runId || "",
            label: selectedOutcome.title?.trim() || "Outcome",
          }
        : null,
  )

  const summary = summarizeActivityView(outcomes)
  const statsReady = !isLoading && !error
  const hasOutcomeFilters = status !== "all" || lifecycle !== "all" || integration.trim() !== ""
  const hasObjectFilters =
    objectType !== "all" || objectDepartment !== "all" || objectStatus !== "all" || objectPriority !== "all"
  const hasActiveFilters = tab === "objects" ? hasObjectFilters : hasOutcomeFilters
  const panelLoading = tab === "objects" ? workObjectsLoading : isLoading
  const panelError = tab === "objects" ? workObjectListError : error
  const currentRows: Array<BusinessOutcomeDto | WorkObjectDto> = tab === "objects" ? workObjects : outcomes
  const selectedIndex =
    tab === "objects"
      ? selectedWorkObject
        ? workObjects.findIndex((o) => o.id === selectedWorkObject.id)
        : -1
      : selectedOutcome
        ? outcomes.findIndex((o) => outcomeKey(o) === outcomeKey(selectedOutcome))
        : -1

  const resetFilters = () => {
    if (tab === "objects") {
      setObjectType("all")
      setObjectDepartment("all")
      setObjectStatus("all")
      setObjectPriority("all")
    } else {
      setStatus("all")
      setLifecycle("all")
      setIntegration("")
    }
  }

  const ask = (prompt: string) =>
    summonWorkspace({ presentation: "compact", selected: undefined, agentScope: null, composerText: prompt, submit: false })

  const retrySelected = async () => {
    if (!selectedOutcome) return
    if (!selectedOutcome.runId) {
      ask(
        `Retry "${selectedOutcome.title ?? "this action"}" safely. First check whether it already took effect so nothing is duplicated, then confirm with me.`,
      )
      return
    }
    try {
      setRetrying(true)
      const result = await runsApi.retry(selectedOutcome.runId)
      toast.success("Retry started")
      await mutate()
      if (result?.run_id) router.push(`/runs/${result.run_id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed")
    } finally {
      setRetrying(false)
    }
  }

  const exportAudit = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const response = await auditApi.export("csv")
      if (!response.ok) throw new Error(`Export failed (${response.status})`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = "activity-audit.csv"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success("Audit exported")
    } catch {
      toast.error("Could not export the audit trail")
    } finally {
      setExporting(false)
    }
  }

  const selectRow = (index: number) => {
    const target = currentRows[index]
    if (!target) return
    if (tab === "objects") setSelectedWorkObjectId((target as WorkObjectDto).id)
    else setSelectedOutcomeId(outcomeKey(target as BusinessOutcomeDto))
    rowRefs.current[index]?.scrollIntoView({ block: "nearest" })
  }
  const pager = (
    <OvPager
      position={selectedIndex + 1}
      count={currentRows.length}
      onPrev={() => selectRow(selectedIndex - 1)}
      onNext={() => selectRow(selectedIndex + 1)}
    />
  )

  // Arrow keys move the selection and follow focus (ARIA listbox pattern).
  const handleListKeyDown = (event: KeyboardEvent<HTMLElement>, index: number) => {
    const lastIndex = currentRows.length - 1
    let next: number | null = null
    if (event.key === "ArrowDown") next = index === lastIndex ? 0 : index + 1
    else if (event.key === "ArrowUp") next = index === 0 ? lastIndex : index - 1
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = lastIndex
    if (next === null) return
    event.preventDefault()
    const target = currentRows[next]
    if (!target) return
    if (tab === "objects") setSelectedWorkObjectId((target as WorkObjectDto).id)
    else setSelectedOutcomeId(outcomeKey(target as BusinessOutcomeDto))
    rowRefs.current[next]?.focus()
    rowRefs.current[next]?.scrollIntoView({ block: "nearest" })
  }

  const verifiedLabel =
    statsReady && summary.completed > 0 && summary.verified >= summary.completed ? "Verified, all of them" : "Verified"

  const stat = (value: number, label: string, onClick: () => void, extra?: { tone?: string; live?: boolean }) => (
    <button type="button" className={cn("ov-stat", extra?.tone)} onClick={onClick}>
      <span className="v">
        {statsReady ? value : <span className="ov-skel-n" />}
        {extra?.live && value > 0 ? <i className="ov-live" aria-hidden /> : null}
      </span>
      <span className="k">{label}</span>
    </button>
  )

  const segments: Array<{ id: ActivityTab; label: string; count?: number }> = [
    { id: "all", label: "All", count: isLoading ? undefined : outcomes.length },
    { id: "objects", label: "Work objects", count: workObjectsLoading ? undefined : workObjects.length },
    { id: "failures", label: "Failures" },
  ]

  return (
    <AppShell>
      <WsPage wide={false}>
        <div className="ov-page" data-composition="operate">
          <section aria-labelledby="activity-hero" className="ov-hero">
            <div className="ov-hero-art">
              {/* eslint-disable-next-line @next/next/no-img-element -- static library scene */}
              <img src="/illustrations/ops-activity.svg" alt="" />
            </div>
            <div className="ov-hero-copy">
              <div className="ov-hero-eb">
                <span className="ov-eyebrow">Operate / Work in motion</span>
                {error ? (
                  <span className="ov-fresh stale" role="status">
                    <i aria-hidden />
                    Could not refresh
                    <button type="button" onClick={() => void mutate()}>
                      Retry
                    </button>
                  </span>
                ) : (
                  <span className="ov-fresh">
                    <i aria-hidden />
                    {isValidating && updatedAt ? "Refreshing..." : updatedLabel(updatedAt, now)}
                  </span>
                )}
              </div>
              <h1 id="activity-hero">Activity</h1>
              <p className="ov-lead">
                Every outcome your agents produce, with the evidence to prove it. Exceptions rise to the top, the rest stays
                out of your way.
              </p>
              <div className="ov-stats">
                {stat(summary.running, "Running", () => { setTab("all"); setStatus("running") }, {
                  tone: summary.running > 0 ? "green" : undefined,
                  live: true,
                })}
                {stat(summary.approval, "Need approval", () => router.push("/approvals"))}
                {stat(summary.completed, "Completed", () => { setTab("all"); setStatus("completed") })}
                {stat(summary.verified, verifiedLabel, () => { setTab("all"); setLifecycle("verified") })}
              </div>
              <div className="ov-actions">
                <button
                  type="button"
                  className="ov-btn dark"
                  onClick={() =>
                    ask(
                      "Explain this work: what is running, what failed and why, and what I should do next. Do not assume completion means verification.",
                    )
                  }
                >
                  <Sparkles size={16} aria-hidden />
                  Explain this work
                </button>
                <button type="button" className="ov-btn" onClick={() => void exportAudit()} disabled={exporting}>
                  <Download size={16} aria-hidden />
                  {exporting ? "Exporting..." : "Export audit"}
                </button>
              </div>
            </div>
          </section>

          <div className="ov-toolbar">
            <div className="ov-seg lg" role="group" aria-label="Activity views">
              {segments.map((item) => (
                <button key={item.id} type="button" aria-pressed={tab === item.id} onClick={() => setTab(item.id)}>
                  {item.label}
                  {typeof item.count === "number" ? <span className="c"> {item.count}</span> : null}
                </button>
              ))}
            </div>
            <span className="sp" />
            {tab === "all" ? (
              <>
                <SelectField label="Status" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
                <SelectField label="Lifecycle" value={lifecycle} onChange={setLifecycle} options={LIFECYCLE_OPTIONS} />
                <input
                  className="ov-input"
                  aria-label="Connector"
                  placeholder="Connector, for example hubspot"
                  value={integration}
                  onChange={(e) => setIntegration(e.target.value)}
                />
              </>
            ) : tab === "objects" ? (
              <>
                <SelectField label="Type" value={objectType} onChange={setObjectType} options={OBJECT_TYPES} />
                <SelectField label="Department" value={objectDepartment} onChange={setObjectDepartment} options={OBJECT_DEPARTMENTS} />
                <SelectField label="Status" value={objectStatus} onChange={setObjectStatus} options={OBJECT_STATUSES} />
                <SelectField label="Priority" value={objectPriority} onChange={setObjectPriority} options={OBJECT_PRIORITIES} />
              </>
            ) : null}
            {tab !== "failures" && hasActiveFilters ? (
              <button type="button" className="ov-linkbtn" onClick={resetFilters}>
                <X size={14} aria-hidden /> Clear filters
              </button>
            ) : null}
          </div>

          {tab === "failures" ? (
            <section className="ov-panel ov-pad" aria-label="Failure alerts">
              <FailureAlertsPanel />
            </section>
          ) : (
            <section aria-labelledby="activity-panel" className="ov-panel">
              <div className="ov-band">
                <div className="ov-band-l">
                  <span className="ov-dots" aria-hidden>
                    <i />
                    <i />
                    <i />
                  </span>
                  <h2 id="activity-panel">{tab === "objects" ? "Work objects" : "Outcomes"}</h2>
                </div>
                {tab === "all" && selectedOutcome?.runId ? (
                  <Link className="ov-band-link" href={`/runs/${selectedOutcome.runId}?trace=1`}>
                    Open run
                    <ExternalLink size={14} aria-hidden />
                  </Link>
                ) : null}
              </div>

              {panelError ? (
                <div className="ov-alert" role="alert" style={{ margin: 16 }}>
                  <span>Could not load {tab === "objects" ? "work objects" : "activity"}.</span>
                  <button
                    type="button"
                    className="ov-btn sm"
                    onClick={() => void (tab === "objects" ? mutateWorkObjects() : mutate())}
                  >
                    Retry
                  </button>
                </div>
              ) : null}

              <div className={cn("ov-split tall swap", mobileDetailOpen && "has-detail")}>
                <div className="ov-list">
                  <div className="ov-list-head">Recent</div>
                  {panelLoading ? (
                    <div className="ov-placeholder" aria-busy="true">
                      <span>Loading...</span>
                    </div>
                  ) : currentRows.length === 0 ? (
                    <div className="ov-empty">
                      <b>
                        {hasActiveFilters
                          ? `No matching ${tab === "objects" ? "work objects" : "activity"}`
                          : tab === "objects"
                            ? "No work objects yet"
                            : "No activity yet"}
                      </b>
                      <span>
                        {hasActiveFilters
                          ? "No results for these filters. Try widening them to see more."
                          : tab === "objects"
                            ? "Complete connector actions in chat or runs and work objects will be attributed here."
                            : "Run a workflow or complete work in chat, and results land here automatically."}
                      </span>
                      {hasActiveFilters ? (
                        <button type="button" className="ov-btn sm" onClick={resetFilters}>
                          Clear filters
                        </button>
                      ) : (
                        <button type="button" className="ov-btn dark sm" onClick={() => ask("")}>
                          Start in chat
                        </button>
                      )}
                    </div>
                  ) : (
                    <div
                      className="ov-items"
                      role="listbox"
                      aria-label={tab === "objects" ? "Work object list" : "Recent activity"}
                    >
                      {tab === "objects"
                        ? workObjects.map((workObject, index) => {
                            const active = selectedWorkObject?.id === workObject.id
                            const tone = statusTone(workObject.status)
                            return (
                              <button
                                key={workObject.id}
                                type="button"
                                role="option"
                                aria-selected={active}
                                aria-current={active}
                                className={cn("ov-item", tone === "red" && "fail")}
                                tabIndex={index === (selectedIndex === -1 ? 0 : selectedIndex) ? 0 : -1}
                                ref={(node) => {
                                  rowRefs.current[index] = node
                                }}
                                onKeyDown={(event) => handleListKeyDown(event, index)}
                                onClick={() => setSelectedWorkObjectId(workObject.id)}
                              >
                                <span className="row">
                                  <span className="t">{workObject.title || "Untitled work object"}</span>
                                  <span className={cn("ov-status", tone)}>
                                    <i aria-hidden />
                                    {humanize(workObject.status || "identified").toLowerCase()}
                                  </span>
                                </span>
                                <span className="s">{workObject.objective || "No objective yet"}</span>
                                <span className="ov-chips">
                                  {workObject.objectType ? <span className="ov-tag">{workObject.objectType}</span> : null}
                                  {workObject.department ? <span className="ov-tag">{workObject.department}</span> : null}
                                  {(workObject.systemsInvolved || []).slice(0, 2).map((sys) => (
                                    <span key={sys} className="ov-tag">
                                      {sys}
                                    </span>
                                  ))}
                                </span>
                              </button>
                            )
                          })
                        : outcomes.map((outcome, index) => {
                            const id = outcomeKey(outcome)
                            const active = selectedOutcome != null && outcomeKey(selectedOutcome) === id
                            const tone = statusTone(outcome.status || outcome.lifecycleState)
                            const tags = [outcome.sections?.evidence?.integration, outcome.source].filter(
                              (t): t is string => typeof t === "string" && t.length > 0,
                            )
                            return (
                              <button
                                key={id}
                                id={`activity-row-${id}`}
                                type="button"
                                role="option"
                                aria-selected={active}
                                aria-current={active}
                                className={cn("ov-item", tone === "red" && "fail", tone === "amber" && "warn")}
                                tabIndex={index === (selectedIndex === -1 ? 0 : selectedIndex) ? 0 : -1}
                                ref={(node) => {
                                  rowRefs.current[index] = node
                                }}
                                onKeyDown={(event) => handleListKeyDown(event, index)}
                                onClick={() => setSelectedOutcomeId(id)}
                              >
                                <span className="row">
                                  <span className="t">{outcome.title || "Untitled outcome"}</span>
                                  {outcome.status || outcome.lifecycleState ? (
                                    <span className={cn("ov-status", tone)}>
                                      <i aria-hidden />
                                      {humanize(outcome.status || outcome.lifecycleState).toLowerCase()}
                                    </span>
                                  ) : null}
                                </span>
                                <span className="s">{outcome.sections?.summary || "No summary"}</span>
                                {tags.length > 0 ? (
                                  <span className="ov-chips">
                                    {tags.map((tag) => (
                                      <span key={tag} className="ov-tag">
                                        {tag}
                                      </span>
                                    ))}
                                  </span>
                                ) : null}
                              </button>
                            )
                          })}
                    </div>
                  )}
                </div>

                <div className="ov-detail">
                  <div className="ov-detail-in">
                    <button
                      type="button"
                      className="ov-btn sm ov-back"
                      onClick={() => {
                        setSelectedOutcomeId(null)
                        setSelectedWorkObjectId(null)
                      }}
                    >
                      <ArrowLeft size={14} aria-hidden />
                      Back to list
                    </button>
                    {panelLoading ? (
                      <div className="ov-placeholder" aria-busy="true">
                        <span>Loading...</span>
                      </div>
                    ) : tab === "objects" && selectedWorkObject ? (
                      <WorkObjectDetail
                        workObject={selectedWorkObject}
                        events={workObjectEvents}
                        loading={workObjectDetailLoading}
                        pager={pager}
                      />
                    ) : tab === "all" && selectedOutcome ? (
                      <OutcomeDetail
                        key={outcomeKey(selectedOutcome)}
                        outcome={selectedOutcome}
                        onRetry={() => void retrySelected()}
                        retrying={retrying}
                        onAsk={ask}
                        pager={pager}
                      />
                    ) : (
                      <div className="ov-placeholder">
                        <b>Nothing selected</b>
                        <span>Pick an item from the list to inspect it.</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </WsPage>
    </AppShell>
  )
}

export default function ActivityPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <CenteredLoader fill="parent" label="Loading activity" />
        </AppShell>
      }
    >
      <ActivityPageInner />
    </Suspense>
  )
}
