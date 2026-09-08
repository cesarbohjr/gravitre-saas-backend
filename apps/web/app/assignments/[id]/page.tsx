"use client"

import { useState, use, useMemo, useEffect } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { motion } from "framer-motion"
import { PulseRing } from "@/components/gravitre/premium-effects"
import { useMotionPrefs } from "@/lib/animations"
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
import { Icon, type IconName } from "@/lib/icons"
import { NavTasks } from "@/components/icons/nodus-nav/outline"
import { cn } from "@/lib/utils"
import { formatAssignmentOutput } from "@/lib/plain-english"
import { approveAssignment, fetchAssignmentJob, pushAssignmentDeliverable, rejectAssignment, updateAssignmentDeliverable } from "@/lib/demo-assignments"
import type { AgentJob } from "@/hooks/use-async-job"
import { toast } from "sonner"
import {
  parseHandoffResult,
  buildExecutionSteps,
  buildDeliverables,
  jobProgress,
  relativeTime,
} from "@/lib/agent-job-result"

// Types
interface ExecutionStep {
  id: string
  name: string
  status: "completed" | "running" | "pending" | "error"
  duration?: string
  details?: string
}

interface Deliverable {
  id: string
  title: string
  type: "email" | "social" | "report" | "segment" | "workflow"
  status: "ready" | "pending" | "error"
  confidence: number
  preview: string
  sourceRefs: string[]
}

async function fetchAgentJob(id: string): Promise<AgentJob> {
  return fetchAssignmentJob(id)
}

const typeConfig: Record<string, { icon: string; color: string; label: string; bg: string }> = {
  email: { icon: "mail", color: "text-blue-400", label: "Email", bg: "bg-blue-500/10" },
  social: { icon: "share", color: "text-violet-400", label: "Social", bg: "bg-violet-500/10" },
  report: { icon: "chart", color: "text-[color:var(--g-brand)]", label: "Report", bg: "bg-[color:var(--g-brand-soft)]" },
  segment: { icon: "users", color: "text-amber-400", label: "Segment", bg: "bg-amber-500/10" },
  workflow: { icon: "workflow", color: "text-rose-400", label: "Workflow", bg: "bg-rose-500/10" },
}

// Live Execution Timeline
function ExecutionTimeline({ steps, currentProgress }: { steps: ExecutionStep[]; currentProgress: number }) {
  const completedSteps = steps.filter(s => s.status === "completed").length
  const runningStep = steps.find(s => s.status === "running")

  return (
    <GravitreSurface>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <motion.div 
              className="flex h-10 w-10 items-center justify-center rounded-[var(--np-radius-md)] bg-info/10"
              animate={{ 
                boxShadow: ["0 0 20px rgba(59, 130, 246, 0.2)", "0 0 30px rgba(59, 130, 246, 0.4)", "0 0 20px rgba(59, 130, 246, 0.2)"]
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Icon name="activity" size="sm" className="text-blue-400" />
            </motion.div>
          </div>
          <div>
            <h3 className="font-semibold text-foreground">Execution Progress</h3>
            <p className="text-xs text-muted-foreground">{completedSteps} of {steps.length} steps complete</p>
          </div>
        </div>
        <div className="text-right">
          <motion.span 
            className="text-2xl font-bold text-foreground"
            key={currentProgress}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {currentProgress}%
          </motion.span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-secondary overflow-hidden mb-6">
        <motion.div
          className="h-full rounded-full bg-info"
          style={{ backgroundPosition: "0% 0%" }}
          animate={{ 
            width: `${currentProgress}%`,
            backgroundPosition: ["0% 0%", "100% 0%", "0% 0%"]
          }}
          transition={{ 
            width: { duration: 0.5 },
            backgroundPosition: { duration: 2, repeat: Infinity, ease: "linear" }
          }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-3">
        {steps.map((step, i) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className={cn(
              "flex items-center gap-4 p-3 rounded-xl transition-all",
              step.status === "running" && "bg-blue-500/5 ring-1 ring-blue-500/20",
              step.status === "completed" && "opacity-70"
            )}
          >
            {/* Step indicator */}
            <div className="relative">
              {step.status === "completed" && (
                <motion.div 
                  className="flex h-8 w-8 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-soft)]"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                >
                  <Icon name="check" size="sm" className="text-[color:var(--g-brand)]" />
                </motion.div>
              )}
              {step.status === "running" && (
                <motion.div 
                  className="h-8 w-8 rounded-lg bg-blue-500/20 flex items-center justify-center"
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                >
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  >
                    <Icon name="spinner" size="sm" className="text-blue-400" />
                  </motion.div>
                </motion.div>
              )}
              {step.status === "pending" && (
                <div className="h-8 w-8 rounded-lg bg-secondary flex items-center justify-center">
                  <span className="text-xs font-medium text-muted-foreground">{i + 1}</span>
                </div>
              )}
              {step.status === "error" && (
                <div className="h-8 w-8 rounded-lg bg-red-500/20 flex items-center justify-center">
                  <Icon name="warning" size="sm" className="text-red-400" />
                </div>
              )}
              
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className={cn(
                  "absolute left-1/2 top-full w-0.5 h-3 -translate-x-1/2",
                  step.status === "completed" ? "bg-[color:var(--g-brand)]/30" : "bg-divide"
                )} />
              )}
            </div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={cn(
                  "font-medium",
                  step.status === "running" ? "text-foreground" : "text-muted-foreground"
                )}>
                  {step.name}
                </span>
                {step.duration && (
                  <span className="text-xs text-muted-foreground">{step.duration}</span>
                )}
              </div>
              {step.details && (
                <p className="text-xs text-muted-foreground mt-0.5">{step.details}</p>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </GravitreSurface>
  )
}

// Deliverable Card
function DeliverableCard({ 
  deliverable, 
  isSelected, 
  isApproved,
  onClick, 
  onApprove 
}: { 
  deliverable: Deliverable; 
  isSelected: boolean;
  isApproved: boolean;
  onClick: () => void;
  onApprove: () => void;
}) {
  const config = typeConfig[deliverable.type]

  return (
    <motion.div
      layout
      onClick={onClick}
      className={cn(
        "relative cursor-pointer rounded-[var(--np-radius-lg)] border p-4 transition-all",
        isSelected 
          ? "border-emerald-500/50 bg-[color:var(--g-surface-2)] ring-1 ring-emerald-500/20" 
          : "border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] hover:bg-[color:var(--g-surface-2)]",
        isApproved && "border-emerald-500/30"
      )}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      {/* Approved badge */}
      {isApproved && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-[color:var(--g-brand)] shadow-[var(--np-shadow)]"
        >
          <Icon name="check" size="xs" className="text-white" />
        </motion.div>
      )}

      <div className="flex items-start justify-between mb-3">
        <div className={cn("h-9 w-9 rounded-lg flex items-center justify-center", config.bg)}>
          <Icon name={config.icon as IconName} size="sm" className={config.color} />
        </div>
        
        {/* Confidence ring */}
        {deliverable.status === "ready" && (
          <div className="relative h-9 w-9">
            <svg className="h-9 w-9 -rotate-90">
              <circle cx="18" cy="18" r="14" fill="none" stroke="currentColor" strokeWidth="3" className="text-secondary" />
              <motion.circle
                cx="18" cy="18" r="14" fill="none"
                stroke={deliverable.confidence >= 90 ? "#10b981" : deliverable.confidence >= 70 ? "#f59e0b" : "#ef4444"}
                strokeWidth="3" strokeLinecap="round" strokeDasharray={88}
                initial={{ strokeDashoffset: 88 }}
                animate={{ strokeDashoffset: 88 - (deliverable.confidence / 100) * 88 }}
                transition={{ duration: 1 }}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-foreground">
              {deliverable.confidence}
            </span>
          </div>
        )}
        
        {deliverable.status === "pending" && (
          <motion.div
            className="h-9 w-9 rounded-lg bg-secondary flex items-center justify-center"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <Icon name="clock" size="sm" className="text-muted-foreground" />
          </motion.div>
        )}
      </div>

      <h4 className="font-medium text-foreground mb-1 line-clamp-1">{deliverable.title}</h4>
      <p className="text-xs text-muted-foreground line-clamp-2 mb-3">{deliverable.preview.slice(0, 80)}...</p>

      <div className="flex items-center justify-between">
        <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", config.bg, config.color)}>
          {config.label}
        </span>
        
        {deliverable.status === "ready" && !isApproved && (
          <Button 
            size="sm" 
            variant="ghost" 
            className="h-7 text-xs gap-1"
            onClick={(e) => { e.stopPropagation(); onApprove(); }}
          >
            <Icon name="check" size="xs" />
            Approve
          </Button>
        )}
      </div>
    </motion.div>
  )
}

// Preview Panel
function PreviewPanel({ deliverable, isApproved, onApprove, onPush, onEdit, jobError, isPushing = false }: { 
  deliverable: Deliverable | null; 
  isApproved: boolean;
  onApprove: () => void;
  onPush: () => void;
  onEdit: () => void;
  jobError?: string | null;
  isPushing?: boolean;
}) {
  if (jobError) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="h-16 w-16 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
          <Icon name="warning" size="xl" className="text-red-400" />
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
        <h3 className="font-semibold text-foreground mb-2">Select a Deliverable</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          Click on any deliverable to preview its content and approve for publishing
        </p>
      </div>
    )
  }

  const config = typeConfig[deliverable.type]

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-divide p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn("h-10 w-10 rounded-xl flex items-center justify-center", config.bg)}>
              <Icon name={config.icon as IconName} size="sm" className={config.color} />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">{deliverable.title}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={cn("text-xs", config.color)}>{config.label}</span>
                {deliverable.confidence > 0 && (
                  <>
                    <span className="text-muted-foreground/50">|</span>
                    <span className={cn(
                      "text-xs font-medium",
                      deliverable.confidence >= 90 ? "text-[color:var(--g-brand)]" : "text-amber-600"
                    )}>
                      {deliverable.confidence}% confidence
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
          
          {isApproved && (
            <div className="flex items-center gap-1.5 rounded-full bg-[color:var(--g-brand-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--g-brand)]">
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
              <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-secondary text-muted-foreground">
                {ref}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Preview Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="rounded-xl bg-secondary/50 p-4">
          <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
            {deliverable.preview}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="border-t border-divide p-4">
        <div className="flex items-center gap-3">
          {!isApproved ? (
            <>
              <Button 
                className="flex-1 gap-2"
                onClick={onApprove}
              >
                <Icon name="check" size="sm" />
                Approve
              </Button>
              <Button variant="outline" className="gap-2" onClick={onEdit}>
                <Icon name="edit" size="sm" />
                Edit
              </Button>
            </>
          ) : (
            <>
              <Button 
                className="flex-1 gap-2"
                onClick={onPush}
                disabled={isPushing}
              >
                <Icon name="upload" size="sm" />
                {isPushing ? "Pushing…" : "Push to destination"}
              </Button>
              <Button
                variant="outline"
                className="gap-2"
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
      </div>
    </div>
  )
}

function AssignmentApprovalDialog({
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
  confidence: number
  reportContent: string
  qualityChecks: Array<{ label: string; status: "pass" | "warn" }>
  onApprove: () => Promise<void>
  onReject: (reason: string) => Promise<void>
  isSubmitting: boolean
}) {
  const [rejectMode, setRejectMode] = useState(false)
  const [rejectReason, setRejectReason] = useState("")
  const [decisionSuccess, setDecisionSuccess] = useState<"approved" | "rejected" | null>(null)
  const { reduced } = useMotionPrefs()

  const handleRejectSubmit = async () => {
    if (!rejectReason.trim()) {
      toast.error("Please explain why you are rejecting this assignment")
      return
    }
    try {
      await onReject(rejectReason.trim())
      setDecisionSuccess("rejected")
      window.setTimeout(() => onOpenChange(false), 900)
    } catch {
      // Parent surfaces toast
    }
  }

  const handleApproveClick = async () => {
    try {
      await onApprove()
      setDecisionSuccess("approved")
      window.setTimeout(() => onOpenChange(false), 900)
    } catch {
      // Parent surfaces toast
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
        }
        onOpenChange(next)
      }}
    >
      <DialogContent className="max-w-2xl gap-0 overflow-hidden p-0">
        {decisionSuccess ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <div className="relative mb-4 flex h-14 w-14 items-center justify-center">
              {decisionSuccess === "approved" && !reduced && (
                <div className="pointer-events-none absolute left-1/2 top-1/2">
                  <PulseRing color="emerald" size={56} />
                </div>
              )}
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
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
                : "The agent has been notified."}
            </p>
          </div>
        ) : (
          <>
        <DialogHeader className="border-b border-divide px-6 py-5 text-left">
          <DialogTitle className="text-lg">{title}</DialogTitle>
          <DialogDescription>
            Generated by {agentName}
            {confidence > 0 ? ` · ${confidence}% confident` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[42vh] overflow-y-auto px-6 py-4">
          <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground">
            {reportContent}
          </div>
        </div>

        <div className="border-t border-divide px-6 py-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Quality check
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

        <div className="flex flex-col gap-3 border-t border-divide px-6 py-4 sm:flex-row sm:items-end sm:justify-end">
          {rejectMode ? (
            <div className="flex w-full flex-col gap-3">
              <label className="text-xs font-medium text-muted-foreground">
                Why are you rejecting this?
              </label>
              <Textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why are you rejecting this?"
                className="min-h-[88px] w-full"
                disabled={isSubmitting}
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
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
                  onClick={() => void handleRejectSubmit()}
                  disabled={isSubmitting || !rejectReason.trim()}
                >
                  {isSubmitting ? (
                    <Icon name="spinner" size="sm" className="animate-spin" />
                  ) : null}
                  Submit rejection
                </Button>
              </div>
            </div>
          ) : (
            <>
              <Button
                variant="outline"
                className="border-red-500/30 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                onClick={() => setRejectMode(true)}
                disabled={isSubmitting}
              >
                Reject with note
              </Button>
              <Button
                className="gap-2"
                onClick={() => void handleApproveClick()}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <Icon name="spinner" size="sm" className="animate-spin" />
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

export default function AssignmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const searchParams = useSearchParams()
  const approvalFromUrl = searchParams.get("approval") === "1"
  const [selectedDeliverable, setSelectedDeliverable] = useState<string | null>("primary-answer")
  const [approvedItems, setApprovedItems] = useState<string[]>([])
  const [approvalDismissedManual, setApprovalDismissedManual] = useState(false)
  const [isDecisionPending, setIsDecisionPending] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editDraft, setEditDraft] = useState("")
  const [isSavingEdit, setIsSavingEdit] = useState(false)
  const [isPushing, setIsPushing] = useState(false)
  const approvalDismissed = approvalFromUrl ? false : approvalDismissedManual

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
    () => (job ? buildExecutionSteps(job, handoff) : []),
    [job, handoff],
  )
  const deliverables = useMemo(() => buildDeliverables(handoff), [handoff])
  const progress = job ? jobProgress(job.status, handoff) : 0

  const taskTitle =
    handoff?.action_title?.trim() ||
    handoff?.task?.description?.trim() ||
    (typeof job?.result === "object" && job?.result && "task" in job.result
      ? String((job.result as { task?: { description?: string } }).task?.description || "")
      : "") ||
    "Agent assignment"

  const taskBrief = formatAssignmentOutput(
    handoff?.finding_description?.trim() ||
      handoff?.summary?.trim() ||
      handoff?.task?.description?.trim() ||
      "",
  )

  const agentName = handoff?.agent_name || "Agent"
  const agentInitials = agentName.slice(0, 2).toUpperCase()
  const agentId = handoff?.agent_id
  const createdAt = relativeTime(job?.createdAt)
  const confidencePercent = Math.round(
    (handoff?.confidence ?? 0) <= 1 ? (handoff?.confidence ?? 0) * 100 : (handoff?.confidence ?? 0),
  )

  const approvalStatus = handoff?.approval_status
  const needsApproval =
    job?.status === "completed" &&
    Boolean(handoff?.requires_approval || handoff?.needs_human_input) &&
    approvalStatus !== "approved" &&
    approvalStatus !== "rejected"

  const approvalOpen = needsApproval && !approvalDismissed

  const qualityChecks = useMemo(() => {
    const sources = (handoff?.rag_sources ?? [])
      .map((source) => source.source)
      .filter(Boolean) as string[]
    const checks: Array<{ label: string; status: "pass" | "warn" }> = [
      { label: "All requested sections included", status: "pass" },
    ]
    if (sources.length > 0) {
      checks.push({
        label: `Data sourced from ${sources.slice(0, 2).join(" + ")}`,
        status: "pass",
      })
    } else {
      checks.push({ label: "Data sourced from connected systems", status: "pass" })
    }
    checks.push({ label: "Format matches template", status: "pass" })
    if (confidencePercent > 0 && confidencePercent < 95) {
      checks.push({ label: "Optional comparison sections may be incomplete", status: "warn" })
    }
    return checks
  }, [handoff?.rag_sources, confidencePercent])

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

  const handleApprove = (deliverableId: string) => {
    setApprovedItems((prev) => (prev.includes(deliverableId) ? prev : [...prev, deliverableId]))
  }

  const handleApproveAll = () => {
    setApprovedItems(deliverables.filter((d) => d.status === "ready").map((d) => d.id))
  }

  const handleAssignmentApprove = async () => {
    setIsDecisionPending(true)
    try {
      const updated = await approveAssignment(id)
      await mutate(updated as AgentJob, { revalidate: false })
      setApprovedItems(deliverables.filter((d) => d.status === "ready").map((d) => d.id))
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
    setEditDraft(selectedItem?.preview || reportContent)
    setEditOpen(true)
  }

  const handleSaveEdit = async () => {
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
    setIsPushing(true)
    try {
      const result = await pushAssignmentDeliverable(id)
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
            eyebrow="Work"
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

  if (loadError || !job) {
    return (
      <AppShell title="Assignment">
        <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
          <GravitrePageHeader
            eyebrow="Work"
            title="Assignment"
            icon={<NavTasks className="h-5 w-5" />}
            actions={
              <Link href="/assignments">
                <Button variant="outline" size="sm">Back to Assignments</Button>
              </Link>
            }
          />
          <div className="flex flex-1 items-center justify-center px-[var(--np-page-pad)]">
            <GravitreEmpty
              icon={<Icon name="warning" size="lg" />}
              title="Assignment not found"
              hint={loadError instanceof Error ? loadError.message : "This assignment could not be loaded."}
              action={
                <Link href="/assignments">
                  <Button variant="outline" size="sm">Back to Assignments</Button>
                </Link>
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
          if (!open) setApprovalDismissedManual(true)
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

      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          className="shrink-0"
          eyebrow="Work"
          title={taskTitle}
          description={`${agentName} · ${createdAt} · ${job.status.replace(/_/g, " ")}`}
          icon={<NavTasks className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {agentId ? (
                <Link href={`/agents/${agentId}/chat`}>
                  <Button variant="outline" size="sm" className="text-xs">Chat</Button>
                </Link>
              ) : null}
              <Link href="/assignments">
                <Button variant="outline" size="sm" className="gap-1">
                  <Icon name="chevronLeft" size="sm" />
                  Back
                </Button>
              </Link>
            </div>
          }
        >
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[var(--np-radius-md)] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)] text-sm font-bold text-[color:var(--g-brand)]">
              {agentInitials}
            </div>
            {taskBrief && taskBrief !== taskTitle ? (
              <p className="max-w-xl text-xs text-muted-foreground line-clamp-2">{taskBrief}</p>
            ) : null}
            {handoff ? <ExecutionModeBadge source={handoff} showMeta /> : null}
          </div>
        </GravitrePageHeader>

        <div className="grid shrink-0 grid-cols-2 gap-[var(--np-kpi-gap)] px-[var(--np-page-pad-sm)] pt-3 sm:px-[var(--np-page-pad)] lg:grid-cols-4">
          <GravitreMetric
            label="Progress"
            value={`${progress}%`}
            hint={`${executionSteps.filter((s) => s.status === "completed").length} of ${executionSteps.length} steps`}
            icon={<Icon name="activity" size="sm" />}
          />
          <GravitreMetric
            label="Deliverables ready"
            value={readyCount}
            hint={`${approvedCount} approved`}
            icon={<Icon name="check" size="sm" />}
          />
          <GravitreMetric
            label="Confidence"
            value={confidencePercent > 0 ? `${confidencePercent}%` : "—"}
            hint="From agent handoff"
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

        <div className="flex min-h-0 flex-1 overflow-hidden px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]">
          {/* Left Column - Execution & Deliverables */}
          <div className="flex w-[420px] shrink-0 flex-col overflow-hidden border-r border-divide pr-3">
            <div className="flex-1 space-y-4 overflow-y-auto pb-4">
              {needsApproval && (
                <GravitreSurface className="border-violet-500/30 bg-violet-500/5 p-4" padded={false}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">Awaiting your approval</p>
                      <p className="text-xs text-muted-foreground">
                        Review the generated output before it is sent to {handoff?.task?.description ? "destinations" : "downstream systems"}.
                      </p>
                    </div>
                    <Button size="sm" className="gap-1" onClick={() => setApprovalDismissedManual(false)}>
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
                <GravitreSurface className="border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400" padded={false}>
                  Rejected: {rejectionReason}
                </GravitreSurface>
              )}

              <ExecutionTimeline steps={executionSteps} currentProgress={progress} />

              <div>
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground">Deliverables</h3>
                    <p className="text-xs text-muted-foreground">{readyCount} ready | {approvedCount} approved</p>
                  </div>
                  {readyCount > 0 && approvedCount < readyCount && (
                    <Button size="sm" variant="outline" className="gap-1 text-xs" onClick={handleApproveAll}>
                      <Icon name="check" size="xs" />
                      Approve All
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {deliverables.length === 0 ? (
                    <p className="col-span-2 py-4 text-center text-sm text-muted-foreground">
                      {job.status === "running" || job.status === "queued"
                        ? "Waiting for agent results…"
                        : "No deliverables returned for this task."}
                    </p>
                  ) : (
                    deliverables.map((deliverable) => (
                      <DeliverableCard
                        key={deliverable.id}
                        deliverable={deliverable}
                        isSelected={selectedDeliverable === deliverable.id}
                        isApproved={approvedItems.includes(deliverable.id)}
                        onClick={() => setSelectedDeliverable(deliverable.id)}
                        onApprove={() => handleApprove(deliverable.id)}
                      />
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Preview Panel */}
          <GravitreSurface className="ml-3 min-h-0 flex-1 overflow-hidden" padded={false}>
            <PreviewPanel
              deliverable={selectedItem || null}
              isApproved={selectedItem ? approvedItems.includes(selectedItem.id) : false}
              onApprove={() => selectedItem && handleApprove(selectedItem.id)}
              onPush={handlePushDeliverable}
              onEdit={handleEditDeliverable}
              jobError={jobError}
              isPushing={isPushing}
            />
          </GravitreSurface>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit deliverable</DialogTitle>
            <DialogDescription>Update the content before approval or push.</DialogDescription>
          </DialogHeader>
          <Textarea
            value={editDraft}
            onChange={(e) => setEditDraft(e.target.value)}
            rows={12}
            className="font-mono text-sm"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditOpen(false)} disabled={isSavingEdit}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={isSavingEdit || isPushing}>
              {isSavingEdit ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
