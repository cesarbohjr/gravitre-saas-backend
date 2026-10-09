"use client"

import { useState, use, useMemo, useRef, type FormEvent, type ReactNode } from "react"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { useAgentDepartments } from "@/lib/use-agent-departments"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { toast } from "sonner"
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  ChevronRight,
  Download,
  Link2,
  Loader2,
  MoreHorizontal,
  Pencil,
  Send,
  X,
} from "lucide-react"
import { usePublishGravitreAISelection, useOptionalGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { approveAssignment, fetchAssignmentJob, pushAssignmentDeliverable, rejectAssignment, updateAssignmentDeliverable } from "@/lib/demo-assignments"
import { cancelAssignmentJob, createAssignment, retryAssignmentJob } from "@/lib/assignments"
import { readableAssignmentText } from "@/lib/assignments-list"
import { deliverableExport, parseDeliverable } from "@/lib/assignment-deliverable"
import { DeliverableEditorDialog } from "@/components/assignments/deliverable-editor"
import { formatAssignmentOutput } from "@/lib/plain-english"
import type { AgentJob } from "@/hooks/use-async-job"
import { parseHandoffResult, buildExecutionSteps } from "@/lib/agent-job-result"
import { ExecutionTimeline, AssignmentApprovalDialog, reportedAssignmentConfidence } from "@/components/assignments/assignment-detail-surfaces"
import { DeliverableReport, OriginalDataDisclosure } from "@/components/assignments/deliverable-report"
import { actionResults, assignmentFlag, reportedIssueText, shortDate, upgradeLinkFrom } from "@/lib/assignment-signals"
import "@/components/assignments/assignments-workspace.css"

type OutcomeTone = "amber" | "red" | "brand" | "neutral"

interface Outcome {
  tone: OutcomeTone
  illustration: string
  eyebrow: string
  title: string
  body: ReactNode
  actions: ReactNode
  role: "alert" | "status"
}

const ACTIVE = ["queued", "running", "paused"]

function DetailShell({ children }: { children: ReactNode }) {
  return (
    <AppShell title="Assignment">
      <WsPage>{children}</WsPage>
    </AppShell>
  )
}

function Crumbs({ current }: { current?: string }) {
  return (
    <nav aria-label="Breadcrumb" className="asgd-crumbs">
      <Link href="/assignments">Assignments</Link>
      {current ? (
        <>
          <span aria-hidden>/</span>
          <span>{current}</span>
        </>
      ) : null}
    </nav>
  )
}

export default function AssignmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const searchParams = useSearchParams()
  const workspace = useOptionalGravitreAIWorkspace()
  const approvalFromUrl = searchParams.get("approval") === "1"
  const [approvalRequested, setApprovalRequested] = useState(approvalFromUrl)
  const [approvalDismissed, setApprovalDismissed] = useState(false)
  const [isDecisionPending, setIsDecisionPending] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [isPushing, setIsPushing] = useState(false)
  const [jobAction, setJobAction] = useState<null | "retry" | "cancel" | "rerun">(null)
  const [activeTab, setActiveTab] = useState<"deliverable" | "actions" | "steps">("deliverable")
  const [traceOpen, setTraceOpen] = useState<boolean | null>(null)
  const [openErrors, setOpenErrors] = useState<Set<string>>(() => new Set())
  const [question, setQuestion] = useState("")
  const deliverableRef = useRef<HTMLElement | null>(null)
  const actionsRef = useRef<HTMLElement | null>(null)
  const stepsRef = useRef<HTMLElement | null>(null)

  const { data: job, error: loadError, isLoading, mutate } = useSWR(
    id ? `agent-job-${id}` : null,
    () => fetchAssignmentJob(id),
    {
      // Poll while the agent is still working; stop once the job settles.
      refreshInterval: (latest) => (latest && ACTIVE.includes(latest.status) ? 2000 : 0),
      revalidateOnFocus: true,
    },
  )

  const handoff = useMemo(() => parseHandoffResult(job ?? null), [job])
  const executionSteps = useMemo(
    () => (job && handoff?.react_trace?.length ? buildExecutionSteps(job, handoff) : []),
    [job, handoff],
  )
  const actions = useMemo(() => actionResults(handoff?.tool_calls), [handoff?.tool_calls])
  const failedActions = actions.filter((row) => !row.ok).length
  const progress =
    typeof handoff?.progress_percent === "number" && Number.isFinite(handoff.progress_percent)
      ? Math.min(100, Math.max(0, handoff.progress_percent))
      : null

  // Read the raw value: the agent may return an object or a JSON string, and
  // humanizing first would destroy the structure we need to present.
  const rawAnswer: unknown = useMemo(() => {
    const record = (job?.result ?? null) as Record<string, unknown> | null
    const answer = record?.answer
    if (answer && (typeof answer === "object" || (typeof answer === "string" && answer.trim()))) return answer
    const summary = record?.summary
    return typeof summary === "string" && summary.trim() ? summary : null
  }, [job?.result])
  const deliverable = useMemo(() => (rawAnswer == null ? null : parseDeliverable(rawAnswer)), [rawAnswer])

  const rawBrief = handoff?.task?.description?.trim() || handoff?.finding_description?.trim() || ""
  const brief = useMemo(() => (rawBrief ? parseDeliverable(rawBrief) : null), [rawBrief])

  const taskTitle =
    readableAssignmentText(handoff?.action_title?.trim() || handoff?.task?.description?.trim() || "") || "Agent assignment"
  const agentName = handoff?.agent_name || "Agent"
  const agentId = handoff?.agent_id
  const departmentOf = useAgentDepartments()
  const createdLabel = shortDate(job?.createdAt, true)
  const confidencePercent = reportedAssignmentConfidence(handoff?.confidence)
  const sources = (handoff?.rag_sources ?? []).map((s) => s.source).filter((s): s is string => Boolean(s))
  const toolCallsUsed =
    handoff?.tool_call_count ?? handoff?.toolCallCount ?? (Array.isArray(handoff?.tool_calls) ? handoff.tool_calls.length : null)
  const toolsAvailable = handoff?.tools_available ?? handoff?.toolsAvailable ?? null
  const destination = (job?.result as Record<string, unknown> | null)?.destination

  const approvalStatus = handoff?.approval_status
  const needsApproval =
    job?.status === "completed" &&
    Boolean(handoff?.requires_approval || handoff?.needs_human_input) &&
    approvalStatus !== "approved" &&
    approvalStatus !== "rejected"
  const approvalOpen = (needsApproval || (approvalRequested && job?.status === "completed")) && approvalRequested && !approvalDismissed
  const issueText = job ? reportedIssueText(job) : null
  const flag = job ? assignmentFlag(job) : null
  const rejectionReason = handoff?.rejection_reason || (job?.status === "cancelled" && job.error ? job.error : null)
  const canPush = job?.status === "completed" && !needsApproval && approvalStatus !== "rejected" && Boolean(deliverable)
  const canEdit = job?.status === "completed" && Boolean(deliverable) && !isDecisionPending && !isSavingEdit && !isPushing
  const canRerun = Boolean(agentId && handoff?.task?.description?.trim())

  usePublishGravitreAISelection(job ? { kind: "assignment", id, label: taskTitle } : null)

  const qualityChecks = useMemo(() => {
    const checks: Array<{ label: string; status: "pass" | "warn" }> = []
    if (sources.length > 0) {
      checks.push({
        label: `Reported sources: ${sources.slice(0, 2).join(" + ")}${sources.length > 2 ? ` and ${sources.length - 2} more` : ""}`,
        status: "pass",
      })
    } else {
      checks.push({ label: "No retrieved sources were reported for this output", status: "warn" })
    }
    return checks
  }, [sources])

  const openReview = () => {
    setApprovalDismissed(false)
    setApprovalRequested(true)
  }

  const handleAssignmentApprove = async () => {
    if (isDecisionPending) return
    setIsDecisionPending(true)
    try {
      const updated = await approveAssignment(id)
      await mutate(updated as AgentJob, { revalidate: false })
      toast.success("Assignment approved")
    } catch (err) {
      toast.error("Failed to approve assignment", { description: err instanceof Error ? err.message : "Please try again." })
      throw err
    } finally {
      setIsDecisionPending(false)
    }
  }

  const handleAssignmentReject = async (reason: string) => {
    if (isDecisionPending) return
    setIsDecisionPending(true)
    try {
      const updated = await rejectAssignment(id, reason)
      await mutate(updated as AgentJob, { revalidate: false })
      toast.success("Assignment rejected")
    } catch (err) {
      toast.error("Failed to reject assignment", { description: err instanceof Error ? err.message : "Please try again." })
      throw err
    } finally {
      setIsDecisionPending(false)
    }
  }

  // Errors are rethrown so the editor keeps the draft open and shows them inline.
  const handleSaveEdit = async (content: string) => {
    if (isSavingEdit) return
    setIsSavingEdit(true)
    try {
      const updated = await updateAssignmentDeliverable(id, content)
      await mutate(updated as AgentJob, { revalidate: true })
      setEditOpen(false)
      toast.success("Deliverable updated")
    } finally {
      setIsSavingEdit(false)
    }
  }

  const handlePush = async () => {
    if (isPushing) return
    setIsPushing(true)
    try {
      const result = await pushAssignmentDeliverable(id)
      if (!result.ok) throw new Error("The destination did not confirm delivery")
      toast.success(result.destination ? `Pushed to ${result.destination}` : "Deliverable pushed to destination")
    } catch (err) {
      toast.error("Push failed", { description: err instanceof Error ? err.message : "Configure a destination on this assignment." })
    } finally {
      setIsPushing(false)
    }
  }

  const handleExport = () => {
    if (!deliverable) return
    const exported = deliverableExport(deliverable)
    const blob = new Blob([exported.body], { type: exported.mime })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `assignment-${id}.${exported.extension}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const handleRetry = async () => {
    if (jobAction) return
    setJobAction("retry")
    try {
      const updated = await retryAssignmentJob(id)
      await mutate(updated, { revalidate: true })
      toast.success(job?.status === "paused" ? "Assignment resumed" : "Assignment queued to run again")
    } catch (err) {
      toast.error("Could not retry", { description: err instanceof Error ? err.message : "Please try again." })
    } finally {
      setJobAction(null)
    }
  }

  const handleCancel = async () => {
    if (jobAction) return
    setJobAction("cancel")
    try {
      const updated = await cancelAssignmentJob(id)
      await mutate(updated, { revalidate: true })
      toast.success("Assignment cancelled")
    } catch (err) {
      toast.error("Could not cancel", { description: err instanceof Error ? err.message : "Please try again." })
    } finally {
      setJobAction(null)
    }
  }

  // A delivered job cannot be re-queued by the API, so "Run again" assigns the same brief to the same agent.
  const handleRerun = async () => {
    const task = handoff?.task?.description?.trim()
    if (jobAction || !agentId || !task) return
    setJobAction("rerun")
    try {
      const { id: nextId } = await createAssignment({
        agentId,
        agentName,
        agentRole: "Agent",
        agentGradient: "",
        task,
        priority: "normal",
      })
      toast.success("Assignment queued again")
      router.push(`/assignments/${nextId}`)
    } catch (err) {
      toast.error("Could not run again", { description: err instanceof Error ? err.message : "Please try again." })
    } finally {
      setJobAction(null)
    }
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href.split("?")[0])
      toast.success("Link copied")
    } catch {
      toast.error("Could not copy the link")
    }
  }

  const askAgent = (event: FormEvent) => {
    event.preventDefault()
    const text = question.trim()
    if (!text || !agentId) return
    if (workspace) {
      workspace.summonWorkspace({
        agentScope: { agentId, name: agentName },
        selected: { kind: "assignment", id, label: taskTitle },
        composerText: text,
        submit: true,
      })
      setQuestion("")
      return
    }
    router.push(`/agents/${agentId}/chat`)
  }

  const goTo = (tab: "deliverable" | "actions" | "steps") => {
    setActiveTab(tab)
    if (tab === "steps") setTraceOpen(true)
    const target = tab === "deliverable" ? deliverableRef.current : tab === "actions" ? actionsRef.current : stepsRef.current
    target?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  const toggleError = (key: string) =>
    setOpenErrors((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  if (isLoading && !job) {
    return (
      <DetailShell>
        <Crumbs />
        <div role="status" className="asgd-loading">
          <Loader2 size={18} className="animate-spin motion-reduce:animate-none" aria-hidden />
          Loading assignment
        </div>
      </DetailShell>
    )
  }

  if (!job) {
    return (
      <DetailShell>
        <Crumbs />
        <div className="asgd-notfound">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library illustration */}
          <img src="/illustrations/moment-error.svg" alt="" data-illustration="moment-error" />
          <h1 className="gv-h2">Assignment not found</h1>
          <p className="gv-hint">{loadError instanceof Error ? loadError.message : "This assignment could not be loaded."}</p>
          <button type="button" className="gv-btn outline" onClick={() => void mutate()}>
            Retry
          </button>
        </div>
      </DetailShell>
    )
  }

  const isActive = ACTIVE.includes(job.status)
  const statusLabel = needsApproval
    ? "Needs your decision"
    : approvalStatus === "approved"
      ? "Approved"
      : approvalStatus === "rejected"
        ? "Rejected"
        : job.status === "completed"
          ? "Delivered"
          : job.status === "queued"
            ? "Queued"
            : job.status === "running"
              ? "Executing"
              : job.status === "paused"
                ? "Paused"
                : job.status === "failed"
                  ? "Failed"
                  : "Cancelled"
  const statusTone = needsApproval ? "amber" : job.status === "running" ? "brand" : job.status === "failed" ? "red" : "neutral"
  const laneCrumb = needsApproval
    ? "Waiting on you"
    : job.status === "running"
      ? "Executing"
      : job.status === "queued" || job.status === "paused"
        ? "Queued"
        : "Delivered"
  const showFlag = flag && flag.label !== statusLabel
  const upgrade = upgradeLinkFrom(issueText) ?? (flag?.needsLook ? upgradeLinkFrom(typeof rawAnswer === "string" ? rawAnswer : null) : null)
  const issueBody = issueText ? formatAssignmentOutput(issueText) || issueText : null

  const otherSource = (
    <Link href="/connectors" className="gv-btn ghost">
      Use another data source
    </Link>
  )
  const upgradeButton = upgrade ? (
    <a href={upgrade.href} target="_blank" rel="noopener noreferrer" className="gv-btn primary">
      {upgrade.label}
      <ArrowUpRight size={16} aria-hidden />
    </a>
  ) : null

  const outcome: Outcome | null = (() => {
    if (needsApproval) {
      return {
        tone: "amber",
        illustration: "moment-request-waiting",
        eyebrow: "Waiting on you",
        title: handoff?.human_input_prompt ? formatAssignmentOutput(handoff.human_input_prompt) : "This output is waiting for your decision",
        body: "Approving records your decision. Nothing is sent until you push the output to a destination.",
        role: "status",
        actions: (
          <>
            <button type="button" className="gv-btn primary" onClick={openReview} disabled={isDecisionPending}>
              Review and decide
            </button>
            <Link href="/approvals" className="gv-btn ghost">
              Open decision queue
            </Link>
          </>
        ),
      }
    }
    if (job.status === "failed") {
      return {
        tone: "amber",
        illustration: "moment-unplugged",
        eyebrow: "Outcome",
        title: "The agent could not finish this assignment",
        body: issueBody ?? "The job stopped without reporting a reason.",
        role: "alert",
        actions: (
          <>
            {upgradeButton}
            <button type="button" className="gv-btn outline" onClick={() => void handleRetry()} disabled={Boolean(jobAction)}>
              {jobAction === "retry" ? "Retrying" : "Retry assignment"}
            </button>
            {otherSource}
          </>
        ),
      }
    }
    if (job.status === "cancelled") {
      return {
        tone: "neutral",
        illustration: "moment-paused-agents",
        eyebrow: "Outcome",
        title: "Cancelled",
        body: rejectionReason ?? "This assignment was cancelled before it finished.",
        role: "status",
        actions: (
          <button type="button" className="gv-btn outline" onClick={() => void handleRetry()} disabled={Boolean(jobAction)}>
            {jobAction === "retry" ? "Retrying" : "Run it again"}
          </button>
        ),
      }
    }
    if (approvalStatus === "rejected") {
      return {
        tone: "red",
        illustration: "moment-error",
        eyebrow: "Outcome",
        title: "Rejected",
        body: rejectionReason ?? "This output was rejected.",
        role: "status",
        actions: canRerun ? (
          <button type="button" className="gv-btn outline" onClick={() => void handleRerun()} disabled={Boolean(jobAction)}>
            {jobAction === "rerun" ? "Assigning" : "Run again"}
          </button>
        ) : null,
      }
    }
    if (job.status === "completed" && flag?.needsLook) {
      const title =
        actions.length > 0 && failedActions > 0
          ? `Delivered, but ${failedActions} of ${actions.length} actions failed`
          : "Delivered with a problem"
      return {
        tone: "amber",
        illustration: "moment-unplugged",
        eyebrow: "Outcome",
        title,
        body: issueBody ?? "Some of the agent's actions did not complete.",
        role: "alert",
        actions: (
          <>
            {upgradeButton}
            {canRerun ? (
              <button type="button" className="gv-btn outline" onClick={() => void handleRerun()} disabled={Boolean(jobAction)}>
                {jobAction === "rerun" ? "Assigning" : "Run again"}
              </button>
            ) : null}
            {otherSource}
          </>
        ),
      }
    }
    if (approvalStatus === "approved") {
      return {
        tone: "brand",
        illustration: "moment-high-five",
        eyebrow: "Outcome",
        title: "Approved",
        body: handoff?.approval_notes ? handoff.approval_notes : "Push the output when you are ready to deliver it.",
        role: "status",
        actions: null,
      }
    }
    if (job.status === "completed") {
      const summary = handoff?.summary ? formatAssignmentOutput(handoff.summary) : ""
      return {
        tone: "brand",
        illustration: "moment-all-clear",
        eyebrow: "Outcome",
        title: "Delivered",
        body: summary && summary !== taskTitle ? summary : "The agent finished this assignment. Review the deliverable below.",
        role: "status",
        actions: null,
      }
    }
    if (isActive) {
      return {
        tone: "neutral",
        illustration: job.status === "running" ? "moment-focus-time" : "moment-paused-agents",
        eyebrow: job.status === "running" ? "Executing" : job.status === "paused" ? "Paused" : "Queued",
        title:
          job.status === "running"
            ? `${agentName} is working on this`
            : job.status === "queued"
              ? "Queued. The agent will start shortly."
              : "Paused",
        body: progress != null ? `Reported progress ${progress}%` : "Results appear here as soon as the agent returns them.",
        role: "status",
        actions:
          job.status === "paused" ? (
            <button type="button" className="gv-btn primary" onClick={() => void handleRetry()} disabled={Boolean(jobAction)}>
              {jobAction === "retry" ? "Resuming" : "Resume"}
            </button>
          ) : null,
      }
    }
    return null
  })()

  const pushNote = !deliverable
    ? null
    : canPush
      ? typeof destination === "string" && destination && destination !== "export"
        ? `Push sends this deliverable to ${destination}.`
        : "Push marks this deliverable as delivered and keeps it ready to export."
      : needsApproval
        ? "Push stays off until you decide on this output."
        : approvalStatus === "rejected"
          ? "Push stays off because this output was rejected."
          : isActive
            ? "Push turns on once the agent returns its output."
            : "Push stays off until the assignment delivers an output."

  const report = deliverable ? <DeliverableReport parsed={deliverable} /> : undefined
  const traceIsOpen = traceOpen ?? (job.status === "running" || job.status === "failed")

  return (
    <DetailShell>
      <AssignmentApprovalDialog
        open={approvalOpen}
        onOpenChange={(open) => {
          if (!open) {
            setApprovalDismissed(true)
            setApprovalRequested(false)
          }
        }}
        title={taskTitle}
        agentName={agentName}
        confidence={confidencePercent}
        reportContent={deliverable?.original || taskTitle}
        report={report}
        qualityChecks={qualityChecks}
        onApprove={handleAssignmentApprove}
        onReject={handleAssignmentReject}
        isSubmitting={isDecisionPending}
      />

      <Crumbs current={laneCrumb} />
      <div className="asgd-head" data-composition="operate">
        <div className="asgd-head-main">
          <h1 className="asgd-title">{taskTitle}</h1>
          <div className="asgd-meta">
            <span className="asgd-agent">
              <DepartmentIcon department={departmentOf({ id: agentId, name: agentName })} size="sm" />
              {agentName}
            </span>
            {createdLabel ? (
              <>
                <span aria-hidden>·</span>
                <span>Created {createdLabel}</span>
                <span aria-hidden>·</span>
              </>
            ) : null}
            <span className={`gv-pill ${statusTone}`}>{statusLabel}</span>
            {showFlag && flag ? <span className={`gv-pill ${flag.tone}`}>{flag.label}</span> : null}
          </div>
        </div>
        <div className="asgd-head-actions">
          {agentId ? (
            <Link href={`/agents/${agentId}/chat`} className="gv-btn outline">
              Ask the agent
            </Link>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="gv-btn outline asgd-more" aria-label="More actions">
                <MoreHorizontal size={18} aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => void copyLink()}>
                <Link2 size={14} aria-hidden />
                Copy link
              </DropdownMenuItem>
              {deliverable ? (
                <DropdownMenuItem onSelect={handleExport}>
                  <Download size={14} aria-hidden />
                  Export deliverable
                </DropdownMenuItem>
              ) : null}
              {!isActive && canRerun ? (
                <DropdownMenuItem onSelect={() => void handleRerun()} disabled={Boolean(jobAction)}>
                  Run again
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuItem asChild>
                <Link href="/approvals">Open decision queue</Link>
              </DropdownMenuItem>
              {isActive ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => void handleCancel()} disabled={Boolean(jobAction)}>
                    <X size={14} aria-hidden />
                    Cancel assignment
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {loadError ? (
        <div role="alert" className="gv-card asg-alert" style={{ marginTop: 0, marginBottom: 16 }}>
          <span>
            <strong>Could not refresh assignment.</strong> Showing the last retrieved assignment. Retry for the current state.
          </span>
          <button type="button" className="gv-btn outline sm" onClick={() => void mutate()}>
            Retry
          </button>
        </div>
      ) : null}

      {outcome ? (
        <section className={`gv-card gv-rise asgd-outcome ${outcome.tone}`} role={outcome.role} data-banner={outcome.tone}>
          <div className="asgd-outcome-art">
            {/* eslint-disable-next-line @next/next/no-img-element -- static library illustration */}
            <img src={`/illustrations/${outcome.illustration}.svg`} alt="" data-illustration={outcome.illustration} />
          </div>
          <div className="asgd-outcome-body">
            <div className="gv-eyebrow">{outcome.eyebrow}</div>
            <h2>{outcome.title}</h2>
            <p className="asgd-outcome-text">{outcome.body}</p>
            {outcome.actions ? <div className="asgd-outcome-actions">{outcome.actions}</div> : null}
          </div>
        </section>
      ) : null}

      <div className="asgd-grid">
        <div className="asgd-main">
          <nav className="gv-tabs" aria-label="Assignment sections">
            <button
              type="button"
              className={`gv-utab${activeTab === "deliverable" ? " on" : ""}`}
              aria-current={activeTab === "deliverable" ? "true" : undefined}
              onClick={() => goTo("deliverable")}
            >
              Deliverable
            </button>
            <button
              type="button"
              className={`gv-utab${activeTab === "actions" ? " on" : ""}`}
              aria-current={activeTab === "actions" ? "true" : undefined}
              onClick={() => goTo("actions")}
            >
              Actions<span className="asgd-tabcount">{actions.length}</span>
            </button>
            <button
              type="button"
              className={`gv-utab${activeTab === "steps" ? " on" : ""}`}
              aria-current={activeTab === "steps" ? "true" : undefined}
              onClick={() => goTo("steps")}
            >
              Steps<span className="asgd-tabcount">{executionSteps.length}</span>
            </button>
          </nav>

          <section id="deliverable" ref={deliverableRef} className="gv-card asgd-section" aria-labelledby="deliverable-heading">
            <div className="asgd-section-head">
              <h3 id="deliverable-heading">Deliverable</h3>
              {deliverable ? (
                <>
                  <button type="button" className="gv-btn outline sm" onClick={() => setEditOpen(true)} disabled={!canEdit}>
                    <Pencil size={14} aria-hidden />
                    Edit
                  </button>
                  <button type="button" className="gv-btn outline sm" onClick={handleExport}>
                    <Download size={14} aria-hidden />
                    Export
                  </button>
                  <button
                    type="button"
                    className="gv-btn outline sm"
                    onClick={() => void handlePush()}
                    disabled={!canPush || isPushing}
                    title={canPush ? undefined : (pushNote ?? undefined)}
                  >
                    {isPushing ? <Loader2 size={14} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <Send size={14} aria-hidden />}
                    {isPushing ? "Pushing" : "Push"}
                  </button>
                </>
              ) : null}
            </div>
            {deliverable ? (
              <>
                <div className="asgd-deliverable">{report}</div>
                {pushNote ? <p className="asgd-note">{pushNote}</p> : null}
                <div className="asgd-original">
                  <OriginalDataDisclosure parsed={deliverable} />
                </div>
              </>
            ) : (
              <p className="asgd-empty-line">
                {isActive
                  ? "Waiting for the agent to return its output."
                  : "The agent did not return a written deliverable for this assignment."}
              </p>
            )}
          </section>

          <section id="actions" ref={actionsRef} className="gv-card asgd-section" aria-labelledby="actions-heading">
            <div className="asgd-section-head">
              <h3 id="actions-heading">Action results</h3>
              {actions.length > 0 ? (
                <span className="asgd-tally">
                  <span className="ok">{actions.length - failedActions} succeeded</span> ·{" "}
                  <span className="bad">{failedActions} failed</span>
                </span>
              ) : null}
            </div>
            {actions.length > 0 ? (
              <>
                <div className="asgd-segbar" role="img" aria-label={`${actions.length - failedActions} succeeded, ${failedActions} failed`}>
                  {actions.map((row) => (
                    <span key={row.key} className={row.ok ? undefined : "bad"} />
                  ))}
                </div>
                <ol className="asgd-acts">
                  {actions.map((row) => (
                    <li key={row.key} className="asgd-act">
                      <span className={`asgd-act-icon${row.ok ? "" : " bad"}`} aria-hidden>
                        {row.ok ? <Check size={14} strokeWidth={2.4} /> : <X size={14} strokeWidth={2.4} />}
                      </span>
                      <div className="asgd-act-main">
                        <div className="asgd-act-name">{row.label}</div>
                        <div className="gv-mono asgd-act-tool">
                          {row.tool} · {row.ok ? "executed" : "failed"}
                        </div>
                      </div>
                      {!row.ok ? (
                        <button
                          type="button"
                          className="asgd-linkbtn"
                          aria-expanded={openErrors.has(row.key)}
                          onClick={() => toggleError(row.key)}
                        >
                          {openErrors.has(row.key) ? "Hide" : "Review"}
                        </button>
                      ) : null}
                      {!row.ok && openErrors.has(row.key) ? (
                        <p className="asgd-act-error">{row.error ? formatAssignmentOutput(row.error) || row.error : "The tool did not report why it failed."}</p>
                      ) : null}
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <p className="asgd-empty-line">
                {isActive ? "Tool actions appear here as the agent runs them." : "No tool actions were reported for this assignment."}
              </p>
            )}
          </section>

          <section id="steps" ref={stepsRef} className="gv-card" style={{ scrollMarginTop: 16 }}>
            <details
              className="asgd-trace"
              open={traceIsOpen}
              onToggle={(event) => setTraceOpen((event.currentTarget as HTMLDetailsElement).open)}
            >
              <summary>
                <ChevronRight size={18} className="chev" aria-hidden />
                <span className="t">Execution trace</span>
                <span className="m">
                  {executionSteps.length} reported step{executionSteps.length === 1 ? "" : "s"} ·{" "}
                  {toolCallsUsed ?? 0} tool call{toolCallsUsed === 1 ? "" : "s"}
                </span>
              </summary>
              <div className="asgd-trace-body">
                <ExecutionTimeline steps={executionSteps} currentProgress={progress} jobStatus={job.status} />
              </div>
            </details>
          </section>
        </div>

        <aside className="asgd-aside" aria-label="Assignment context">
          <div className="gv-card asgd-side">
            <div className="gv-eyebrow">Brief</div>
            {brief ? (
              brief.format === "structured" ? (
                <div className="asgd-side-text">
                  <DeliverableReport parsed={brief} />
                  <OriginalDataDisclosure parsed={brief} />
                </div>
              ) : (
                <p className="asgd-side-text">{brief.original}</p>
              )
            ) : (
              <p className="asgd-side-text gv-hint">No brief was recorded.</p>
            )}
          </div>

          <div className="gv-card asgd-side">
            <div className="gv-eyebrow">Trust signals</div>
            <div style={{ marginTop: 14 }}>
              <div className="asgd-row">
                <span className="l">Confidence, agent reported</span>
                <strong>{confidencePercent != null ? `${confidencePercent}%` : "Not reported"}</strong>
              </div>
              {confidencePercent != null ? (
                <>
                  <div
                    className="asgd-meter"
                    role="meter"
                    aria-label="Agent reported confidence"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={confidencePercent}
                  >
                    <span style={{ left: `${confidencePercent}%` }} />
                  </div>
                  <div className="asgd-meter-scale" aria-hidden>
                    <span>Low</span>
                    <span>Medium</span>
                    <span>High</span>
                  </div>
                </>
              ) : null}
            </div>
            <div className="asgd-row sep">
              <span className="l">Tool calls</span>
              <span>
                {toolCallsUsed != null ? (
                  <>
                    <strong>{toolCallsUsed}</strong>
                    {toolsAvailable != null ? <span className="l"> of {toolsAvailable} available</span> : null}
                  </>
                ) : (
                  <span className="l">Not reported</span>
                )}
              </span>
            </div>
            {sources.length > 0 ? (
              <ul className="asgd-sources" aria-label={`${sources.length} reported sources`}>
                {sources.slice(0, 8).map((source) => (
                  <li key={source}>
                    <Link2 size={13} aria-hidden style={{ marginTop: 3, flex: "0 0 auto" }} />
                    <span>{source}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="asgd-warn">
                <AlertTriangle size={16} aria-hidden style={{ flex: "0 0 auto", marginTop: 1 }} />
                No retrieved sources were reported for this output.
              </div>
            )}
            {handoff ? (
              <div style={{ marginTop: 14 }}>
                <ExecutionModeBadge source={handoff} showMeta />
              </div>
            ) : null}
          </div>

          {agentId ? (
            <div id="ask" className="gv-card asgd-side">
              <div className="gv-eyebrow">Ask {agentName}</div>
              <form onSubmit={askAgent}>
                <label className="gv-field asgd-ask">
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask about this assignment"
                    aria-label={`Ask ${agentName}`}
                  />
                  <button type="submit" className="gv-btn primary sm" disabled={!question.trim()}>
                    Ask
                  </button>
                </label>
              </form>
            </div>
          ) : null}
        </aside>
      </div>

      {editOpen && deliverable ? (
        <DeliverableEditorDialog
          open
          onOpenChange={setEditOpen}
          parsed={deliverable}
          approved={approvalStatus === "approved"}
          isSaving={isSavingEdit}
          onSave={handleSaveEdit}
        />
      ) : null}
    </DetailShell>
  )
}
