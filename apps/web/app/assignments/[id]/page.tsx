"use client"

import { useState, use, useMemo, type ReactNode } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
import { toast } from "sonner"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { usePublishGravitreAISelection } from "@/components/gravitre/ai-workspace-provider"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreEmpty } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { approveAssignment, fetchAssignmentJob, pushAssignmentDeliverable, rejectAssignment, updateAssignmentDeliverable } from "@/lib/demo-assignments"
import { readableAssignmentText } from "@/lib/assignments-list"
import { parseDeliverable } from "@/lib/assignment-deliverable"
import { formatAssignmentOutput } from "@/lib/plain-english"
import type { AgentJob } from "@/hooks/use-async-job"
import { parseHandoffResult, buildExecutionSteps, relativeTime } from "@/lib/agent-job-result"
import { ExecutionTimeline, AssignmentApprovalDialog, reportedAssignmentConfidence } from "@/components/assignments/assignment-detail-surfaces"
import { DeliverableReport, OriginalDataDisclosure } from "@/components/assignments/deliverable-report"

type Tone = "attention" | "danger" | "positive" | "neutral" | "live"

const TONE_CLASS: Record<Tone, string> = {
  attention: "border-[color:var(--g-approval)]/40 bg-[color:var(--g-approval-soft)] text-foreground",
  danger: "border-destructive/30 bg-destructive/5 text-foreground",
  positive: "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] text-foreground",
  neutral: "border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] text-foreground",
  live: "border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] text-foreground",
}

const TONE_ICON_CLASS: Record<Tone, string> = {
  attention: "text-[color:var(--g-approval)]",
  danger: "text-destructive",
  positive: "text-[color:var(--g-brand)]",
  neutral: "text-muted-foreground",
  live: "text-[color:var(--g-brand)]",
}

function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 rounded-full border px-2 text-[12px] font-medium", TONE_CLASS[tone])}>
      <span aria-hidden className={cn("size-1.5 rounded-full bg-current", TONE_ICON_CLASS[tone])} />
      {children}
    </span>
  )
}

function Banner({ tone, icon, title, body, action }: { tone: Tone; icon: IconName; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      data-banner={tone}
      className={cn("flex flex-col gap-3 rounded-[var(--g-radius-card,10px)] border p-4 sm:flex-row sm:items-center sm:justify-between", TONE_CLASS[tone])}
    >
      <div className="flex min-w-0 items-start gap-3">
        <Icon
          name={icon}
          size="md"
          className={cn("mt-0.5 shrink-0", TONE_ICON_CLASS[tone], icon === "spinner" && "animate-spin motion-reduce:animate-none")}
        />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-[14px] font-semibold">{title}</p>
          {body ? <div className="text-pretty text-[13px] leading-relaxed text-muted-foreground">{body}</div> : null}
        </div>
      </div>
      {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
    </div>
  )
}

function AsideSection({ title, children, meta }: { title: string; children: ReactNode; meta?: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 border-t border-[color:var(--g-border-subtle)] pt-4 first:border-t-0 first:pt-0">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[13px] font-semibold text-foreground">{title}</h2>
        {meta ? <span className="text-[12px] text-muted-foreground">{meta}</span> : null}
      </div>
      {children}
    </section>
  )
}

function DetailShell({ children }: { children: ReactNode }) {
  return (
    <AppShell title="Assignment">
      <div className="flex min-h-full w-full flex-col bg-[color:var(--g-canvas)] pb-[calc(80px+env(safe-area-inset-bottom))] lg:pb-8">
        {children}
      </div>
    </AppShell>
  )
}

function BackLink() {
  return (
    <Link
      href="/assignments"
      className="inline-flex min-h-11 items-center gap-1 self-start text-[13px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:min-h-8"
    >
      <Icon name="chevronLeft" size="sm" />
      Assignments
    </Link>
  )
}

export default function AssignmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const searchParams = useSearchParams()
  const approvalFromUrl = searchParams.get("approval") === "1"
  const [approvalRequested, setApprovalRequested] = useState(approvalFromUrl)
  const [approvalDismissed, setApprovalDismissed] = useState(false)
  const [isDecisionPending, setIsDecisionPending] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editDraft, setEditDraft] = useState("")
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [isPushing, setIsPushing] = useState(false)

  const { data: job, error: loadError, isLoading, mutate } = useSWR(
    id ? `agent-job-${id}` : null,
    () => fetchAssignmentJob(id),
    {
      refreshInterval: (latest) => (latest && ["queued", "running", "paused"].includes(latest.status) ? 2000 : 0),
      revalidateOnFocus: true,
    },
  )

  const handoff = useMemo(() => parseHandoffResult(job ?? null), [job])
  const executionSteps = useMemo(
    () => (job && handoff?.react_trace?.length ? buildExecutionSteps(job, handoff) : []),
    [job, handoff],
  )
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
  const createdAt = relativeTime(job?.createdAt)
  const confidencePercent = reportedAssignmentConfidence(handoff?.confidence)
  const sources = (handoff?.rag_sources ?? []).map((s) => s.source).filter((s): s is string => Boolean(s))
  const proposedActions = (handoff?.recommended_actions ?? [])
    .map((action) => formatAssignmentOutput(action) || String(action).trim())
    .filter(Boolean)

  const approvalStatus = handoff?.approval_status
  const needsApproval =
    job?.status === "completed" &&
    Boolean(handoff?.requires_approval || handoff?.needs_human_input) &&
    approvalStatus !== "approved" &&
    approvalStatus !== "rejected"
  const approvalOpen = (needsApproval || (approvalRequested && job?.status === "completed")) && approvalRequested && !approvalDismissed
  const jobError = job?.status === "failed" ? job.error || handoff?.error || "The agent task failed." : null
  const rejectionReason = handoff?.rejection_reason || (job?.status === "cancelled" && job.error ? job.error : null)
  const canPush = job?.status === "completed" && !needsApproval && approvalStatus !== "rejected" && Boolean(deliverable)
  const canEdit = job?.status === "completed" && Boolean(deliverable) && !isDecisionPending && !isSavingEdit && !isPushing

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

  const handleEdit = () => {
    if (!deliverable) return
    // Edit the original payload so structured output keeps its shape.
    setEditDraft(deliverable.originalJson ?? deliverable.original)
    setEditOpen(true)
  }

  const handleSaveEdit = async () => {
    if (isSavingEdit) return
    const trimmed = editDraft.trim()
    if (!trimmed) {
      toast.error("Deliverable content cannot be empty")
      return
    }
    setIsSavingEdit(true)
    try {
      const updated = await updateAssignmentDeliverable(id, trimmed)
      await mutate(updated as AgentJob, { revalidate: true })
      setEditOpen(false)
      toast.success("Deliverable updated")
    } catch (err) {
      toast.error("Failed to save edits", { description: err instanceof Error ? err.message : "Please try again." })
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
    const isJson = deliverable.originalJson != null
    const blob = new Blob([deliverable.originalJson ?? deliverable.original], { type: isJson ? "application/json" : "text/plain" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `assignment-${id}.${isJson ? "json" : "txt"}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading && !job) {
    return (
      <DetailShell>
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-[var(--np-page-pad-sm)] pt-4 sm:px-[var(--np-page-pad)]">
          <BackLink />
          <div role="status" className="flex items-center gap-2 py-16 text-[14px] text-muted-foreground">
            <Icon name="spinner" size="md" className="animate-spin motion-reduce:animate-none" />
            Loading assignment…
          </div>
        </div>
      </DetailShell>
    )
  }

  if (!job) {
    return (
      <DetailShell>
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-[var(--np-page-pad-sm)] pt-4 sm:px-[var(--np-page-pad)]">
          <BackLink />
          <GravitreEmpty
            icon={<Icon name="warning" size="lg" />}
            title="Assignment not found"
            hint={loadError instanceof Error ? loadError.message : "This assignment could not be loaded."}
            action={
              <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>
                Retry
              </Button>
            }
          />
        </div>
      </DetailShell>
    )
  }

  const statusTone: Tone = needsApproval
    ? "attention"
    : job.status === "failed" || approvalStatus === "rejected" || job.status === "cancelled"
      ? "danger"
      : job.status === "running" || job.status === "queued" || job.status === "paused"
        ? "live"
        : approvalStatus === "approved"
          ? "positive"
          : "neutral"
  const statusLabel = needsApproval
    ? "Needs your decision"
    : approvalStatus === "approved"
      ? "Approved"
      : approvalStatus === "rejected"
        ? "Rejected"
        : job.status === "completed"
          ? "Delivered"
          : job.status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())

  const report = deliverable ? <DeliverableReport parsed={deliverable} /> : undefined

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

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-[var(--np-page-pad-sm)] pt-4 sm:px-[var(--np-page-pad)]" data-composition="operate">
        <header className="flex flex-col gap-3">
          <BackLink />
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="flex min-w-0 flex-col gap-2">
              <h1 className="text-balance break-words text-[20px] font-semibold leading-snug text-foreground md:text-[22px]">
                {taskTitle}
              </h1>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
                <AgentIdentityAvatar agent={{ name: agentName }} size="sm" showStatusDot={false} />
                <span className="text-foreground">{agentName}</span>
                <span aria-hidden>·</span>
                <span>Created {createdAt}</span>
                <StatusPill tone={statusTone}>{statusLabel}</StatusPill>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {agentId ? (
                <Button asChild variant="outline" size="sm" className="min-h-11 md:min-h-9">
                  <Link href={`/agents/${agentId}/chat`}>Ask {agentName}</Link>
                </Button>
              ) : null}
            </div>
          </div>
        </header>

        {loadError ? (
          <WorkSectionErrorCard
            title="Could not refresh assignment"
            message="Showing the last retrieved assignment. Retry for the current state."
            onRetry={() => void mutate()}
          />
        ) : null}

        {needsApproval ? (
          <Banner
            tone="attention"
            icon="approvals"
            title={handoff?.human_input_prompt ? formatAssignmentOutput(handoff.human_input_prompt) : "This output is waiting for your decision"}
            body="Approving records your decision. Nothing is sent until you push the output to a destination."
            action={
              <Button className="min-h-11 md:min-h-9" onClick={openReview} disabled={isDecisionPending}>
                Review and decide
              </Button>
            }
          />
        ) : jobError ? (
          <Banner
            tone="danger"
            icon="warning"
            title="The agent could not finish this assignment"
            body={formatAssignmentOutput(jobError) || jobError}
            action={
              agentId ? (
                <Button asChild variant="outline" className="min-h-11 md:min-h-9">
                  <Link href={`/agents/${agentId}/chat`}>Ask {agentName}</Link>
                </Button>
              ) : undefined
            }
          />
        ) : approvalStatus === "rejected" ? (
          <Banner tone="danger" icon="close" title="Rejected" body={rejectionReason ?? "This output was rejected."} />
        ) : approvalStatus === "approved" ? (
          <Banner
            tone="positive"
            icon="checkCircle"
            title="Approved"
            body={handoff?.approval_notes ? handoff.approval_notes : "Push the output when you are ready to deliver it."}
          />
        ) : job.status === "running" || job.status === "queued" || job.status === "paused" ? (
          <Banner
            tone="live"
            icon={job.status === "running" ? "spinner" : "clock"}
            title={job.status === "running" ? `${agentName} is working on this` : job.status === "queued" ? "Queued — the agent will start shortly" : "Paused"}
            body={progress != null ? `Reported progress ${progress}%` : "Results appear here as soon as the agent returns them."}
          />
        ) : null}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_360px]">
          <main className="flex min-w-0 flex-col gap-4" aria-labelledby="deliverable-heading">
            <section className="flex flex-col gap-4 rounded-[var(--g-radius-card,10px)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 md:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 id="deliverable-heading" className="text-[16px] font-semibold text-foreground">
                  Deliverable
                </h2>
                {deliverable ? (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" size="sm" className="min-h-11 gap-1.5 md:min-h-8" onClick={handleEdit} disabled={!canEdit}>
                      <Icon name="edit" size="xs" />
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" className="min-h-11 gap-1.5 md:min-h-8" onClick={handleExport}>
                      <Icon name="download" size="xs" />
                      Export
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="min-h-11 gap-1.5 md:min-h-8"
                      onClick={() => void handlePush()}
                      disabled={!canPush || isPushing}
                      title={needsApproval ? "Decide on this output before pushing it" : undefined}
                    >
                      <Icon name={isPushing ? "spinner" : "send"} size="xs" className={isPushing ? "animate-spin motion-reduce:animate-none" : undefined} />
                      {isPushing ? "Pushing…" : "Push"}
                    </Button>
                  </div>
                ) : null}
              </div>

              {deliverable ? (
                <>
                  {report}
                  <OriginalDataDisclosure parsed={deliverable} />
                </>
              ) : (
                <p className="text-[14px] text-muted-foreground">
                  {job.status === "running" || job.status === "queued"
                    ? "Waiting for the agent to return its output."
                    : "The agent did not return a written deliverable for this assignment."}
                </p>
              )}
            </section>

            {proposedActions.length > 0 ? (
              <section className="flex flex-col gap-3 rounded-[var(--g-radius-card,10px)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 md:p-6">
                <h2 className="text-[14px] font-semibold text-foreground">
                  Proposed actions <span className="font-normal tabular-nums text-muted-foreground">{proposedActions.length}</span>
                </h2>
                <ul className="flex flex-col gap-2">
                  {proposedActions.map((action, index) => (
                    <li key={index} className="flex items-start gap-2 text-[14px] leading-relaxed text-foreground">
                      <Icon name="workflow" size="sm" className="mt-1 shrink-0 text-muted-foreground" />
                      <span className="break-words">{action}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </main>

          <aside className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4 lg:self-start" aria-label="Assignment context">
            <AsideSection title="Brief">
              {brief ? (
                brief.format === "structured" ? (
                  <div className="flex flex-col gap-3 text-[13px]">
                    <DeliverableReport parsed={brief} />
                    <OriginalDataDisclosure parsed={brief} />
                  </div>
                ) : (
                  <p className="text-pretty break-words text-[13px] leading-relaxed text-foreground">{brief.original}</p>
                )
              ) : (
                <p className="text-[13px] text-muted-foreground">No brief was recorded.</p>
              )}
            </AsideSection>

            <AsideSection title="Evidence" meta={sources.length ? `${sources.length} sources` : undefined}>
              {sources.length > 0 ? (
                <ul className="flex flex-col gap-1.5">
                  {sources.slice(0, 8).map((source) => (
                    <li key={source} className="flex items-start gap-2 text-[13px] text-foreground">
                      <Icon name="link" size="xs" className="mt-1 shrink-0 text-muted-foreground" />
                      <span className="break-all">{source}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="flex items-start gap-2 text-[13px] text-muted-foreground">
                  <Icon name="warning" size="xs" className="mt-1 shrink-0 text-[color:var(--g-approval)]" />
                  No retrieved sources were reported for this output.
                </p>
              )}
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                <dt className="text-muted-foreground">Confidence</dt>
                <dd className="text-foreground">{confidencePercent != null ? `${confidencePercent}% (agent-reported)` : "Not reported"}</dd>
                <dt className="text-muted-foreground">Tool calls</dt>
                <dd className="tabular-nums text-foreground">{handoff?.tool_call_count ?? handoff?.toolCallCount ?? handoff?.tool_calls?.length ?? 0}</dd>
              </dl>
              {handoff ? <ExecutionModeBadge source={handoff} showMeta /> : null}
            </AsideSection>

            <AsideSection title="Execution">
              <details className="group" open={job.status === "running" || job.status === "failed"}>
                <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground md:min-h-8 [&::-webkit-details-marker]:hidden">
                  <Icon name="chevronRight" size="sm" className="transition-transform group-open:rotate-90 motion-reduce:transition-none" />
                  {executionSteps.length ? `${executionSteps.length} reported steps` : "Trace details"}
                </summary>
                <div className="pt-2">
                  <ExecutionTimeline steps={executionSteps} currentProgress={progress} jobStatus={job.status} />
                </div>
              </details>
            </AsideSection>
          </aside>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={(open) => { if (!isSavingEdit) setEditOpen(open) }}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit deliverable</DialogTitle>
            <DialogDescription>
              {deliverable?.format === "structured"
                ? "Edit the structured output. Keep it valid JSON so it stays readable."
                : "Update the content before approval or push."}
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={editDraft}
            onChange={(e) => setEditDraft(e.target.value)}
            rows={14}
            aria-label="Deliverable content"
            disabled={isSavingEdit}
            className="font-mono text-sm"
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" className="min-h-11" onClick={() => setEditOpen(false)} disabled={isSavingEdit}>
              Cancel
            </Button>
            <Button className="min-h-11" onClick={() => void handleSaveEdit()} disabled={isSavingEdit || isPushing}>
              {isSavingEdit ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </DetailShell>
  )
}
