"use client"

import { useState, use, useMemo } from "react"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { ExecutionModeBadge } from "@/components/intelligence/execution-mode-badge"
import { Icon } from "@/lib/icons"
import { NavTasks } from "@/components/icons/nodus-nav/outline"
import { formatAssignmentOutput } from "@/lib/plain-english"
import { approveAssignment, fetchAssignmentJob, pushAssignmentDeliverable, rejectAssignment, updateAssignmentDeliverable } from "@/lib/demo-assignments"
import { readableAssignmentText } from "@/lib/assignments-list"
import type { AgentJob } from "@/hooks/use-async-job"
import { toast } from "sonner"
import {
  parseHandoffResult,
  buildExecutionSteps,
  buildDeliverables,
  relativeTime,
} from "@/lib/agent-job-result"

import { ExecutionTimeline, DeliverableCard, PreviewPanel, AssignmentApprovalDialog, reportedAssignmentConfidence } from "@/components/assignments/assignment-detail-surfaces"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { useIsMobile } from "@/hooks/use-mobile"

async function fetchAgentJob(id: string): Promise<AgentJob> { return fetchAssignmentJob(id) }

export default function AssignmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const searchParams = useSearchParams()
  const approvalFromUrl = searchParams.get("approval") === "1"
  const [selectedDeliverable, setSelectedDeliverable] = useState<string | null>("primary-answer")
  const compact = useIsMobile(1024)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [approvalRequested, setApprovalRequested] = useState(approvalFromUrl)
  const [approvalDismissedManual, setApprovalDismissedManual] = useState(false)
  const [isDecisionPending, setIsDecisionPending] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editDraft, setEditDraft] = useState("")
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [isPushing, setIsPushing] = useState(false)
  const approvalDismissed = approvalDismissedManual

  const { data: job, error: loadError, isLoading, mutate } = useSWR(
    id ? `agent-job-${id}` : null,
    () => fetchAgentJob(id),
    {
      refreshInterval: (latest) =>
        latest && ["queued", "running", "paused"].includes(latest.status) ? 2000 : 0,
      revalidateOnFocus: true,
    },
  )

  const handoff = useMemo(() => parseHandoffResult(job ?? null), [job])
  const executionSteps = useMemo(
    () => (job && handoff?.react_trace?.length ? buildExecutionSteps(job, handoff) : []),
    [job, handoff],
  )
  const deliverables = useMemo(() => buildDeliverables(handoff).map(item => ({ ...item, confidence: item.id === "primary-answer" ? reportedAssignmentConfidence(handoff?.confidence) : null })), [handoff])
  const progress = typeof handoff?.progress_percent === "number" && Number.isFinite(handoff.progress_percent) ? Math.min(100, Math.max(0, handoff.progress_percent)) : null

  const taskTitle =
    readableAssignmentText(
      handoff?.action_title?.trim() ||
        handoff?.task?.description?.trim() ||
        (typeof job?.result === "object" && job?.result && "task" in job.result
          ? String((job.result as { task?: { description?: string } }).task?.description || "")
          : ""),
    ) || "Agent assignment"

  const taskBrief = formatAssignmentOutput(
    handoff?.finding_description?.trim() ||
      handoff?.summary?.trim() ||
      handoff?.task?.description?.trim() ||
      "",
  )

  const agentName = handoff?.agent_name || "Agent"
  const agentId = handoff?.agent_id
  const createdAt = relativeTime(job?.createdAt)
  const confidencePercent = reportedAssignmentConfidence(handoff?.confidence)

  const approvalStatus = handoff?.approval_status
  const needsApproval =
    job?.status === "completed" &&
    Boolean(handoff?.requires_approval || handoff?.needs_human_input) &&
    approvalStatus !== "approved" &&
    approvalStatus !== "rejected"

  const approvalOpen = (needsApproval || (approvalRequested && job?.status === "completed")) && !approvalDismissed
  const approvedItems = approvalStatus === "approved" ? deliverables.filter(d => d.status === "ready").map(d => d.id) : []

  const qualityChecks = useMemo(() => {
    const sources = (handoff?.rag_sources ?? [])
      .map((source) => source.source)
      .filter(Boolean) as string[]
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
  }, [handoff?.rag_sources])

  const reportContent = formatAssignmentOutput(
    handoff?.answer?.trim() ||
      handoff?.summary?.trim() ||
      deliverables[0]?.preview ||
      taskTitle,
  )

  const selectedItem = deliverables.find((d) => d.id === selectedDeliverable) ?? deliverables[0] ?? null
  const readyCount = deliverables.filter((d) => d.status === "ready").length
  const approvedCount = approvedItems.length
  const jobError = job?.status === "failed" ? (job.error || handoff?.error || "The agent task failed.") : null
  const rejectionReason =
    handoff?.rejection_reason ||
    (job?.status === "cancelled" && job.error ? job.error : null)

  const requestApprovalReview = () => {
    setInspectorOpen(false)
    setApprovalDismissedManual(false)
    setApprovalRequested(true)
  }

  const handleAssignmentApprove = async () => {
    if (isDecisionPending) return
    setApprovalRequested(true)
    setIsDecisionPending(true)
    try {
      const updated = await approveAssignment(id)
      await mutate(updated as AgentJob, { revalidate: false })
      toast.success("Assignment approved")
    } catch (err) {
      toast.error("Failed to approve assignment", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
      throw err
    } finally {
      setIsDecisionPending(false)
    }
  }

  const handleAssignmentReject = async (reason: string) => {
    if (isDecisionPending) return
    setApprovalRequested(true)
    setIsDecisionPending(true)
    try {
      const updated = await rejectAssignment(id, reason)
      await mutate(updated as AgentJob, { revalidate: false })
      toast.success("Assignment rejected")
    } catch (err) {
      toast.error("Failed to reject assignment", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
      throw err
    } finally {
      setIsDecisionPending(false)
    }
  }

  const handleEditDeliverable = () => {
    setInspectorOpen(false)
    setEditDraft(selectedItem?.preview || reportContent)
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
      toast.error("Failed to save edits", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    } finally {
      setIsSavingEdit(false)
    }
  }

  const handlePushDeliverable = async () => {
    if (isPushing) return
    setIsPushing(true)
    try {
      const result = await pushAssignmentDeliverable(id)
      if (!result.ok) throw new Error("The destination did not confirm delivery")
      toast.success(
        result.destination
          ? `Pushed to ${result.destination}`
          : "Deliverable pushed to destination",
      )
    } catch (err) {
      toast.error("Push failed", {
        description: err instanceof Error ? err.message : "Configure a destination on this assignment.",
      })
    } finally {
      setIsPushing(false)
    }
  }

  if (isLoading && !job) {
    return (
      <AppShell title="Assignment">
        <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
          <GravitrePageHeader
            title="Assignment"
            description="Loading…"
            icon={<NavTasks className="h-5 w-5" />}
          />
          <div className="flex flex-1 items-center justify-center px-[var(--np-page-pad)]">
            <Icon name="spinner" size="lg" className="text-muted-foreground animate-spin" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (!job) {
    return (
      <AppShell title="Assignment">
        <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
          <GravitrePageHeader
            title="Assignment"
            icon={<NavTasks className="h-5 w-5" />}
            actions={
              <Button asChild variant="outline" size="sm" className="min-h-11">
                <Link href="/assignments">Back to assignments</Link>
              </Button>
            }
          />
          <div className="flex flex-1 items-center justify-center px-[var(--np-page-pad)]">
            <GravitreEmpty
              icon={<Icon name="warning" size="lg" />}
              title="Assignment not found"
              hint={loadError instanceof Error ? loadError.message : "This assignment could not be loaded."}
              action={
                <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry</Button>
              }
            />
          </div>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Assignment">
      <AssignmentApprovalDialog
        open={approvalOpen}
        onOpenChange={(open) => {
          if (!open) { setApprovalDismissedManual(true); setApprovalRequested(false) }
        }}
        title={taskTitle}
        agentName={agentName}
        confidence={confidencePercent}
        reportContent={reportContent}
        qualityChecks={qualityChecks}
        onApprove={handleAssignmentApprove}
        onReject={handleAssignmentReject}
        isSubmitting={isDecisionPending}
      />

      <div className="flex min-h-full w-full flex-col bg-[color:var(--g-canvas)] pb-[calc(80px+env(safe-area-inset-bottom))] lg:h-full lg:min-h-0 lg:pb-0" data-composition="operate">
        <GravitrePageHeader
          className="shrink-0"
          title={taskTitle}
          description={`${agentName} · ${createdAt} · ${job.status.replace(/_/g, " ")}`}
          icon={<NavTasks className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {agentId ? (
                <Button asChild variant="outline" size="sm" className="min-h-11">
                  <Link href={`/agents/${agentId}/chat`}>Chat</Link>
                </Button>
              ) : null}
              <Button asChild variant="ghost" size="sm" className="min-h-11 gap-1">
                <Link href="/assignments">
                  <Icon name="chevronLeft" size="sm" />
                  Back
                </Link>
              </Button>
            </div>
          }
        >
          <div className="flex flex-wrap items-center gap-3">
            <AgentIdentityAvatar agent={{ name: agentName }} size="md" showStatusDot={false} />
            {taskBrief && taskBrief !== taskTitle ? (
              <p className="max-w-xl text-xs text-muted-foreground line-clamp-2">{taskBrief}</p>
            ) : null}
            {handoff ? <ExecutionModeBadge source={handoff} showMeta /> : null}
          </div>
        </GravitrePageHeader>

        <div className="grid shrink-0 grid-cols-1 sm:grid-cols-2 gap-[var(--np-kpi-gap)] px-[var(--np-page-pad-sm)] pt-3 sm:px-[var(--np-page-pad)] lg:grid-cols-4">
          <GravitreMetric
            label="Reported progress"
            value={progress == null ? "Not reported" : `${progress}%`}
            hint={executionSteps.length ? `${executionSteps.length} reported trace steps` : "Step-level trace not reported"}
            icon={<Icon name="activity" size="sm" />}
          />
          <GravitreMetric
            label="Deliverables ready"
            value={readyCount}
            hint={`${approvedCount} approved`}
            icon={<Icon name="check" size="sm" />}
          />
          <GravitreMetric
            label="Agent-reported confidence"
            value={confidencePercent != null ? `${confidencePercent}%` : "Not reported"}
            hint="Self-reported in the agent handoff, not verified"
            icon={<Icon name="shield" size="sm" />}
          />
          <GravitreMetric
            label="Status"
            value={job.status.replace(/_/g, " ")}
            hint={needsApproval ? "Needs approval" : "Live status"}
            warning={needsApproval}
            icon={<Icon name="clock" size="sm" />}
          />
        </div>

        {loadError ? <div className="px-[var(--np-page-pad-sm)] pt-3 sm:px-[var(--np-page-pad)]"><WorkSectionErrorCard title="Could not refresh assignment" message="Showing the last retrieved assignment. Retry for the current state." onRetry={() => void mutate()} /></div> : null}
        <div className="flex min-h-0 flex-col lg:flex-row lg:flex-1 lg:overflow-hidden px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
          {/* Left Column - Execution & Deliverables */}
          <div className="flex min-w-0 flex-col lg:w-[380px] xl:w-[420px] lg:shrink-0 lg:overflow-hidden lg:border-r lg:border-divide lg:pr-3">
            <div className="space-y-4 pb-4 lg:flex-1 lg:overflow-y-auto">
              {needsApproval && (
                <GravitreSurface className="border-[color:var(--g-warmth)] bg-[color:var(--g-surface-1)] p-4" padded={false}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">Awaiting your approval</p>
                      <p className="text-xs text-muted-foreground">
                        Review the generated output before it is sent to {handoff?.task?.description ? "destinations" : "downstream systems"}.
                      </p>
                    </div>
                    <Button size="sm" className="min-h-11 gap-1" onClick={requestApprovalReview}>
                      Review
                    </Button>
                  </div>
                </GravitreSurface>
              )}

              {approvalStatus === "approved" && (
                <GravitreSurface className="border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] p-4 text-sm text-[color:var(--g-brand)]" padded={false}>
                  <div className="flex items-center gap-2">
                    <Icon name="check" size="sm" />
                    Approved and ready to deliver
                  </div>
                </GravitreSurface>
              )}

              {approvalStatus === "rejected" && rejectionReason && (
                <GravitreSurface className="border-red-500/30 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400" padded={false}>
                  Rejected: {rejectionReason}
                </GravitreSurface>
              )}

              <ExecutionTimeline steps={executionSteps} currentProgress={progress} jobStatus={job.status} />

              <div>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground">Deliverables</h3>
                    <p className="text-xs text-muted-foreground">{readyCount} ready | {approvedCount} approved</p>
                  </div>
                  {readyCount > 0 && approvedCount < readyCount && job.status === "completed" && approvalStatus !== "rejected" && (
                    <Button size="sm" variant="outline" className="min-h-11 gap-1 text-xs" onClick={requestApprovalReview}>
                      <Icon name="check" size="xs" />
                      Review assignment
                    </Button>
                  )}
                </div>

                <ul className="divide-y divide-divide border-y border-divide">
                  {deliverables.length === 0 ? (
                    <li className="py-4 text-center text-sm text-muted-foreground">
                      {job.status === "running" || job.status === "queued"
                        ? "Waiting for agent results…"
                        : "No deliverables returned for this task."}
                    </li>
                  ) : (
                    deliverables.map((deliverable) => (
                      <DeliverableCard
                        key={deliverable.id}
                        deliverable={deliverable}
                        isSelected={selectedItem?.id === deliverable.id}
                        isApproved={approvedItems.includes(deliverable.id)}
                        onClick={() => { setSelectedDeliverable(deliverable.id); setInspectorOpen(true) }}
                        onApprove={requestApprovalReview}
                        canReview={job.status === "completed" && approvalStatus !== "rejected" && !isDecisionPending}
                      />
                    ))
                  )}
                </ul>
              </div>
            </div>
          </div>

          {/* Right Column - Preview Panel */}
          <SelectionInspector open={compact ? inspectorOpen : true} onOpenChange={setInspectorOpen} title={selectedItem?.title ?? "Assignment output"} description="Inspect the returned content and sources before reviewing the assignment." className="ml-3 min-h-0 flex-1 overflow-y-auto">
          <GravitreSurface className="min-h-0" padded={false}>
            <PreviewPanel
              deliverable={selectedItem || null}
              isApproved={selectedItem ? approvedItems.includes(selectedItem.id) : false}
              onApprove={requestApprovalReview}
              canReview={job.status === "completed" && approvalStatus !== "rejected" && !isDecisionPending}
              canEdit={selectedItem?.id === "primary-answer" && job.status === "completed" && !isDecisionPending && !isSavingEdit && !isPushing}
              onPush={handlePushDeliverable}
              onEdit={handleEditDeliverable}
              jobError={jobError}
              isPushing={isPushing}
            />
          </GravitreSurface>
          </SelectionInspector>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={(open) => { if (!isSavingEdit) setEditOpen(open) }}>
        <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit deliverable</DialogTitle>
            <DialogDescription>Update the content before approval or push.</DialogDescription>
          </DialogHeader>
          <Textarea
            value={editDraft}
            onChange={(e) => setEditDraft(e.target.value)}
            rows={12}
            aria-label="Deliverable content"
            disabled={isSavingEdit}
            className="font-mono text-sm"
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="outline" className="min-h-11" onClick={() => setEditOpen(false)} disabled={isSavingEdit}>
              Cancel
            </Button>
            <Button className="min-h-11" onClick={handleSaveEdit} disabled={isSavingEdit || isPushing}>
              {isSavingEdit ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
