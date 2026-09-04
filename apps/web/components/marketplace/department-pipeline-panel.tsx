"use client"

import useSWR from "swr"
import { useState } from "react"
import { cn } from "@/lib/utils"
import { departmentPipelinesApi } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { Switch } from "@/components/ui/switch"
import { CheckCircle2, Circle, AlertTriangle, Loader2, Clock } from "lucide-react"
import { toast } from "sonner"

export type DepartmentPipelineStage = {
  stageId: string
  label: string
  status: "not_started" | "in_progress" | "completed" | "blocked" | "skipped"
  detail?: string
  requiresNewCapability?: boolean
}

export type DepartmentPipelineView = {
  pipelineId: string
  department: string
  displayName: string
  tagline: string
  connectAndGoReady?: boolean
  syncBackPolicy?: {
    syncTiming: "immediate" | "defer_to_milestone"
    deferMilestoneStageId?: string | null
    defaultDeferMilestoneStageId?: string | null
  }
  stageStatuses?: DepartmentPipelineStage[]
  honestGaps?: string[]
}

function statusIcon(status: DepartmentPipelineStage["status"]) {
  switch (status) {
    case "completed":
      return CheckCircle2
    case "in_progress":
      return Loader2
    case "blocked":
      return AlertTriangle
    case "skipped":
      return Clock
    default:
      return Circle
  }
}

function statusTone(status: DepartmentPipelineStage["status"]) {
  switch (status) {
    case "completed":
      return "text-success"
    case "in_progress":
      return "text-primary"
    case "blocked":
      return "text-destructive"
    case "skipped":
      return "text-muted-foreground"
    default:
      return "text-muted-foreground"
  }
}

function SyncBackPolicyControl({
  department,
  policy,
  onUpdated,
}: {
  department: string
  policy?: DepartmentPipelineView["syncBackPolicy"]
  onUpdated?: () => void
}) {
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const [saving, setSaving] = useState(false)
  const deferred = policy?.syncTiming === "defer_to_milestone"
  const milestoneLabel = (
    policy?.deferMilestoneStageId ??
    policy?.defaultDeferMilestoneStageId ??
    "milestone"
  ).replace(/_/g, " ")

  if (adminLoading || !isAdmin) return null

  const handleToggle = async (checked: boolean) => {
    setSaving(true)
    try {
      await departmentPipelinesApi.updateSyncBackPolicy({
        department,
        sync_timing: checked ? "defer_to_milestone" : "immediate",
        defer_milestone_stage_id: checked
          ? policy?.defaultDeferMilestoneStageId ?? policy?.deferMilestoneStageId ?? null
          : null,
      })
      toast.success(
        checked
          ? `CRM sync deferred until ${milestoneLabel}`
          : "CRM sync set to immediate (verified)",
      )
      onUpdated?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update sync policy")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-3 flex items-start justify-between gap-3 rounded-xl border border-border/70 bg-muted/20 px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-xs font-medium text-foreground">Sync-back timing (admin)</p>
        <p className="text-[11px] text-muted-foreground">
          {deferred
            ? `Writes to the system of record wait until ${milestoneLabel}. F6 verification unchanged.`
            : "Verified writes sync immediately on approval (default)."}
        </p>
      </div>
      <Switch
        checked={deferred}
        disabled={saving}
        onCheckedChange={handleToggle}
        aria-label="Defer CRM sync until pipeline milestone"
      />
    </div>
  )
}

export function DepartmentPipelinePanel({
  pipeline,
  compact = false,
  onPolicyUpdated,
}: {
  pipeline: DepartmentPipelineView
  compact?: boolean
  onPolicyUpdated?: () => void
}) {
  const stages = pipeline.stageStatuses ?? []
  const syncLabel =
    pipeline.syncBackPolicy?.syncTiming === "defer_to_milestone"
      ? `Sync deferred until ${(pipeline.syncBackPolicy.deferMilestoneStageId ?? "milestone").replace(/_/g, " ")}`
      : "Sync to system of record: immediate (verified)"

  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-card",
        compact ? "p-4" : "p-5",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Department pipeline
          </p>
          <h3 className="text-base font-semibold text-foreground">{pipeline.displayName}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{pipeline.tagline}</p>
        </div>
        {pipeline.connectAndGoReady ? (
          <span className="rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
            Connect-and-go ready
          </span>
        ) : null}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">{syncLabel}</p>

      <SyncBackPolicyControl
        department={pipeline.department}
        policy={pipeline.syncBackPolicy}
        onUpdated={onPolicyUpdated}
      />

      <ol className={cn("mt-4 space-y-2", compact && "mt-3")}>
        {stages.map((stage, index) => {
          const Icon = statusIcon(stage.status)
          return (
            <li
              key={stage.stageId}
              className="flex items-start gap-3 rounded-xl border border-border/60 bg-muted/20 px-3 py-2.5"
            >
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-background text-xs font-semibold text-muted-foreground">
                {index + 1}
              </span>
              <Icon
                className={cn(
                  "mt-1 h-4 w-4 shrink-0",
                  statusTone(stage.status),
                  stage.status === "in_progress" && "animate-spin",
                )}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{stage.label}</p>
                {stage.detail ? (
                  <p className="text-xs text-muted-foreground">{stage.detail}</p>
                ) : null}
                {stage.requiresNewCapability ? (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    Partial — see honest gaps below
                  </p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>

      {pipeline.honestGaps?.length ? (
        <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Honest gaps</p>
          <ul className="mt-1 list-disc pl-4">
            {pipeline.honestGaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export function DepartmentPipelineByDepartment({ department }: { department: string }) {
  const normalized = department.trim().toLowerCase()
  const key = normalized && normalized !== "general" ? `dept-pipeline:${normalized}` : null
  const { data, error, isLoading, mutate } = useSWR(key, () =>
    departmentPipelinesApi.byDepartment(normalized),
  )

  if (!normalized || normalized === "general") return null

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-border p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading pipeline…
      </div>
    )
  }
  if (error || !data?.pipeline) return null
  return (
    <DepartmentPipelinePanel
      pipeline={data.pipeline as unknown as DepartmentPipelineView}
      compact
      onPolicyUpdated={() => void mutate()}
    />
  )
}
