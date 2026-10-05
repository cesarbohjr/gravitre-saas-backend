"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { Icon, type IconName } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

export function reportedAssignmentConfidence(raw: unknown): number | null {
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw < 0 || raw > 100) return null
  return Math.round(raw <= 1 ? raw * 100 : raw)
}

// Types
interface ExecutionStep {
  id: string
  name: string
  status: "completed" | "running" | "pending" | "error"
  duration?: string
  details?: string
}

export interface Deliverable {
  id: string
  title: string
  type: "email" | "social" | "report" | "segment" | "workflow"
  status: "ready" | "pending" | "error"
  confidence: number | null
  preview: string
  sourceRefs: string[]
}

const typeConfig: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  email: { icon: "mail", color: "text-[color:var(--g-electric)]", label: "Email", bg: "bg-secondary" },
  social: { icon: "share", color: "text-[color:var(--g-text-muted)]", label: "Social", bg: "bg-secondary" },
  report: { icon: "chart", color: "text-[color:var(--g-brand)]", label: "Report", bg: "bg-[color:var(--g-brand-soft)]" },
  segment: { icon: "users", color: "text-[color:var(--g-warmth)]", label: "Segment", bg: "bg-secondary" },
  workflow: { icon: "workflow", color: "text-[color:var(--g-brand-active)]", label: "Workflow", bg: "bg-[color:var(--g-brand-soft)]" },
}

// The trace stays quiet at rest; motion belongs only to a running step.
export function ExecutionTimeline({ steps, currentProgress, jobStatus }: { steps: ExecutionStep[]; currentProgress: number | null; jobStatus?: string }) {
  const { reduced } = useMotionPrefs()
  const labels = { completed: "Completed", running: "Running", pending: "Pending", error: "Failed" }
  return (
    <section aria-label="Execution progress" className="border-y border-divide py-4">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-[family-name:var(--font-space-grotesk)] text-lg font-medium">Execution trace</h2>
        <span className="text-xs text-muted-foreground">{steps.length ? `${steps.filter(s => s.status === "completed").length} of ${steps.length} complete` : "No trace reported"} · {currentProgress == null ? "Progress not reported" : `Reported progress ${currentProgress}%`}</span>
      </div>
      {currentProgress != null ? <div role="progressbar" aria-label="Reported execution progress" aria-valuenow={currentProgress} aria-valuemin={0} aria-valuemax={100} className="mb-4 h-1 overflow-hidden bg-secondary">
        <div className="h-full bg-[color:var(--g-electric)] transition-[width] duration-200 motion-reduce:transition-none" style={{ width: `${Math.min(100, Math.max(0, currentProgress))}%` }} />
      </div> : null}
      {steps.length === 0 ? <p className="text-sm text-muted-foreground">Step-level trace not reported.{jobStatus ? ` Assignment status: ${jobStatus.replaceAll("_", " ")}.` : ""}</p> : null}
      <ol className="space-y-0">
        {steps.map((step, i) => (
          <li key={step.id} className="relative flex min-w-0 items-start gap-3 py-3">
            {i < steps.length - 1 ? <span aria-hidden className="absolute left-4 top-11 bottom-0 w-px bg-divide" /> : null}
            <div className={cn("relative flex size-8 shrink-0 items-center justify-center rounded-[var(--np-radius-md)]", step.status === "completed" ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)]" : step.status === "error" ? "bg-destructive/10 text-destructive" : "bg-secondary text-muted-foreground")}>
              <Icon name={step.status === "completed" ? "check" : step.status === "error" ? "warning" : step.status === "running" ? "spinner" : "clock"} size="sm" className={step.status === "running" && !reduced ? "animate-spin motion-reduce:animate-none" : undefined} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="break-words text-sm font-medium">{step.name}</p>
              {step.details ? <p className="mt-1 break-words text-xs text-muted-foreground">{step.details}</p> : null}
              <p className="mt-1 text-xs text-muted-foreground">{labels[step.status]}{step.duration ? ` · ${step.duration}` : ""}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

// Separate selection and assignment review are keyboard-accessible controls.
export function DeliverableCard({ deliverable, isSelected, isApproved, onClick, onApprove, canReview = true }: {
  deliverable: Deliverable; isSelected: boolean; isApproved: boolean; onClick: () => void; onApprove: () => void; canReview?: boolean
}) {
  const config = typeConfig[deliverable.type]
  return (
    <li className={cn("min-w-0 border-l-2 py-3", isSelected ? "border-[color:var(--g-brand)] bg-[color:var(--g-surface-2)]" : "border-transparent")}>
      <button type="button" onClick={onClick} aria-pressed={isSelected} className="flex min-h-11 w-full min-w-0 items-start gap-3 px-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
        <Icon name={config.icon as IconName} size="sm" className="mt-1 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1">
          <span className="block break-words text-sm font-medium">{deliverable.title}</span>
          <span className="mt-1 block line-clamp-2 break-words text-xs text-muted-foreground">{deliverable.preview}</span>
          <span className="mt-2 block text-xs text-muted-foreground">{config.label} · {deliverable.status === "ready" ? "Ready" : deliverable.status === "error" ? "Failed" : "Pending"}</span>
        </span>
      </button>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-3 pl-10">
        {deliverable.confidence != null ? <span className="text-xs text-muted-foreground">{deliverable.confidence}% agent-reported · unverified</span> : null}
        {isApproved ? <span className="text-xs font-medium text-[color:var(--g-brand-active)]">Assignment approved</span> : deliverable.status === "ready" && canReview ? <Button size="sm" variant="ghost" className="min-h-11 text-xs" onClick={onApprove}>Review assignment</Button> : null}
      </div>
    </li>
  )
}

// Preview Panel
export function PreviewPanel({ deliverable, isApproved, onApprove, onPush, onEdit, jobError, isPushing = false, canReview = true, canEdit = true }: { 
  deliverable: Deliverable | null; 
  isApproved: boolean;
  onApprove: () => void;
  onPush: () => void;
  onEdit: () => void;
  jobError?: string | null;
  isPushing?: boolean;
  canReview?: boolean;
  canEdit?: boolean;
}) {
  if (jobError && !deliverable) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="h-16 w-16 rounded-2xl bg-destructive/10 flex items-center justify-center mb-4">
          <Icon name="warning" size="xl" className="text-destructive" />
        </div>
        <h3 className="font-semibold text-foreground mb-2">Task failed</h3>
        <p className="text-sm text-muted-foreground max-w-md">{jobError}</p>
      </div>
    )
  }

  if (!deliverable) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="h-16 w-16 rounded-2xl bg-secondary flex items-center justify-center mb-4">
          <Icon name="eye" size="xl" className="text-muted-foreground" />
        </div>
        <h3 className="font-semibold text-foreground mb-2">Select a deliverable</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          Click on any deliverable to preview its content and approve for publishing
        </p>
      </div>
    )
  }

  const config = typeConfig[deliverable.type]

  return (
    <div className="h-full min-w-0 flex flex-col">
      {jobError ? <p role="alert" className="border-b border-divide p-4 text-sm text-destructive">Task failed: {jobError}. Returned output remains available for inspection.</p> : null}
      {/* Header */}
      <div className="border-b border-divide p-4">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3 mb-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center", config.bg)}>
              <Icon name={config.icon as IconName} size="sm" className={config.color} />
            </div>
            <div className="min-w-0">
              <h3 className="break-words font-semibold text-foreground">{deliverable.title}</h3>
              <div className="flex flex-wrap items-center gap-2 mt-0.5">
                <span className={cn("text-xs", config.color)}>{config.label}</span>
                {deliverable.confidence != null && (
                  <>
                    <span className="text-muted-foreground/50">|</span>
                    <span className={cn(
                      "text-xs font-medium",
                      "text-muted-foreground"
                    )}>
                      {deliverable.confidence}% agent-reported confidence
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          
          {isApproved && (
            <div className="flex items-center gap-1.5 rounded-[4px] bg-[color:var(--g-brand-soft)] px-1.5 py-0.5 text-xs font-medium text-[color:var(--g-brand)]">
              <Icon name="check" size="xs" />
              Approved
            </div>
          )}
        </div>

        {/* Source references */}
        {deliverable.sourceRefs.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground">Sources:</span>
            {deliverable.sourceRefs.map((ref, i) => (
              <span key={i} className="max-w-full break-all text-xs px-2 py-0.5 rounded-md bg-secondary text-muted-foreground">
                {ref}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Preview Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="rounded-xl bg-secondary/50 p-4">
          <div className="break-words whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
            {deliverable.preview}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="border-t border-divide p-4">
        <div className="flex flex-wrap items-center gap-3">
          {!isApproved ? (
            <>
              <Button 
                className="min-h-11 flex-1 gap-2"
                onClick={onApprove}
                disabled={!canReview || deliverable.status !== "ready"}
              >
                <Icon name="check" size="sm" />
                Review assignment
              </Button>
              <Button variant="outline" className="min-h-11 gap-2" onClick={onEdit} disabled={!canEdit}>
                <Icon name="edit" size="sm" />
                Edit
              </Button>
            </>
          ) : (
            <>
              <Button 
                className="min-h-11 flex-1 gap-2"
                onClick={onPush}
                disabled={isPushing || !canEdit}
              >
                <Icon name="upload" size="sm" />
                {isPushing ? "Pushing…" : "Push to destination"}
              </Button>
              <Button
                variant="outline"
                className="min-h-11 gap-2"
                onClick={() => {
                  const text = deliverable.preview || ""
                  const blob = new Blob([text], { type: "text/plain;charset=utf-8" })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement("a")
                  a.href = url
                  a.download = `${deliverable.title.replace(/[^\w\-]+/g, "_").slice(0, 48) || "assignment"}.txt`
                  a.click()
                  URL.revokeObjectURL(url)
                }}
              >
                <Icon name="download" size="sm" />
                Export
              </Button>
            </>
          )}
        </div>
        {!canEdit ? <p className="mt-2 text-xs text-muted-foreground">Editing and delivery apply to the primary assignment response.</p> : null}
      </div>
    </div>
  )
}

export function AssignmentApprovalDialog({
  open,
  onOpenChange,
  title,
  agentName,
  confidence,
  reportContent,
  qualityChecks,
  onApprove,
  onReject,
  isSubmitting,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  agentName: string
  confidence: number | null
  reportContent: string
  qualityChecks: Array<{ label: string; status: "pass" | "warn" }>
  onApprove: () => Promise<void>
  onReject: (reason: string) => Promise<void>
  isSubmitting: boolean
}) {
  const [decisionError, setDecisionError] = useState<string | null>(null)
  const [rejectMode, setRejectMode] = useState(false)
  const [rejectReason, setRejectReason] = useState("")
  const [decisionSuccess, setDecisionSuccess] = useState<"approved" | "rejected" | null>(null)
  const { reduced } = useMotionPrefs()

  const handleRejectSubmit = async () => {
    if (!rejectReason.trim()) {
      toast.error("Please explain why you are rejecting this assignment")
      return
    }
    setDecisionError(null)
    try {
      await onReject(rejectReason.trim())
      setDecisionSuccess("rejected")
    } catch (error) {
      setDecisionError(error instanceof Error ? error.message : "Could not save the assignment decision. Try again.")
    }
  }

  const handleApproveClick = async () => {
    setDecisionError(null)
    try {
      await onApprove()
      setDecisionSuccess("approved")
    } catch (error) {
      setDecisionError(error instanceof Error ? error.message : "Could not save the assignment decision. Try again.")
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (isSubmitting) return
        if (!next) {
          setRejectMode(false)
          setRejectReason("")
          setDecisionSuccess(null)
          setDecisionError(null)
        }
        onOpenChange(next)
      }}
    >
      <DialogContent showCloseButton={!isSubmitting} className="max-h-[calc(100dvh-2rem)] max-w-2xl gap-0 overflow-y-auto p-0">
        {decisionSuccess ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <DialogTitle className="sr-only">Assignment decision saved</DialogTitle>
            <DialogDescription className="sr-only">The approval service returned the updated assignment.</DialogDescription>
            <div className="relative mb-4 flex h-14 w-14 items-center justify-center">

              <motion.div
                initial={reduced ? false : { scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className={cn(
                  "relative flex h-14 w-14 items-center justify-center rounded-full",
                  decisionSuccess === "approved" ? "bg-[color:var(--g-brand-soft)]" : "bg-destructive/15",
                )}
              >
                <Icon
                  name={decisionSuccess === "approved" ? "check" : "warning"}
                  size="lg"
                  className={decisionSuccess === "approved" ? "text-[color:var(--g-brand)]" : "text-destructive"}
                />
              </motion.div>
            </div>
            <p className="text-lg font-semibold text-foreground">
              {decisionSuccess === "approved" ? "Approved" : "Rejected"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {decisionSuccess === "approved"
                ? "Outputs are cleared for delivery."
                : "The rejection was saved on this assignment."}
            </p>
            <Button className="mt-6 min-h-11" onClick={() => { setDecisionSuccess(null); setRejectMode(false); setRejectReason(""); onOpenChange(false) }}>Done</Button>
          </div>
        ) : (
          <>
        <DialogHeader className="border-b border-divide px-6 py-5 pr-16 text-left">
          <DialogTitle className="text-lg">{title}</DialogTitle>
          <DialogDescription>
            Generated by {agentName}
            {confidence != null ? ` · agent-reported confidence ${confidence}%` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[42vh] overflow-y-auto px-6 py-4">
          <div className="break-words whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
            {reportContent}
          </div>
        </div>

        <div className="border-t border-divide px-6 py-4">
          <p className="mb-3 text-xs font-medium text-muted-foreground">
            Evidence
          </p>
          <ul className="space-y-2">
            {qualityChecks.map((check) => (
              <li key={check.label} className="flex items-start gap-2 text-sm">
                <span className={check.status === "pass" ? "text-[color:var(--g-brand)]" : "text-amber-600"}>
                  {check.status === "pass" ? "✓" : "⚠"}
                </span>
                <span className="text-foreground">{check.label}</span>
              </li>
            ))}
          </ul>
        </div>

        {decisionError ? <p role="alert" className="px-6 pb-4 text-sm text-destructive">{decisionError}</p> : null}
        {isSubmitting ? <p role="status" className="px-6 pb-4 text-sm text-muted-foreground">Saving your decision…</p> : null}
        <div className="flex flex-col gap-3 border-t border-divide px-6 py-4 sm:flex-row sm:items-end sm:justify-end">
          {rejectMode ? (
            <div className="flex w-full flex-col gap-3">
              <label htmlFor="assignment-rejection-reason" className="text-xs font-medium text-muted-foreground">
                Why are you rejecting this?
              </label>
              <Textarea
                id="assignment-rejection-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why are you rejecting this?"
                className="min-h-[88px] w-full"
                disabled={isSubmitting}
                autoFocus
              />
              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  variant="outline"
                  className="min-h-11"
                  onClick={() => {
                    setRejectMode(false)
                    setRejectReason("")
                  }}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  className="min-h-11"
                  onClick={() => void handleRejectSubmit()}
                  disabled={isSubmitting || !rejectReason.trim()}
                >
                  {isSubmitting ? (
                    <Icon name="spinner" size="sm" className="animate-spin motion-reduce:animate-none" />
                  ) : null}
                  Submit rejection
                </Button>
              </div>
            </div>
          ) : (
            <>
              <Button
                variant="outline"
                className="min-h-11 border-destructive/30 text-destructive hover:bg-destructive/10"
                onClick={() => setRejectMode(true)}
                disabled={isSubmitting}
              >
                Reject with note
              </Button>
              <Button
                className="min-h-11 gap-2"
                onClick={() => void handleApproveClick()}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Icon name="spinner" size="sm" className="animate-spin motion-reduce:animate-none" />
                ) : (
                  <Icon name="check" size="sm" />
                )}
                Approve →
              </Button>
            </>
          )}
        </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

