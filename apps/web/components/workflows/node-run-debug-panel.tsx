"use client"

import useSWR from "swr"
import { businessOutcomesApi, runsApi } from "@/lib/api"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Skeleton } from "@/components/ui/skeleton"

export function NodeRunDebugPanel({
  runId,
  nodeId,
  nodeName,
}: {
  runId: string
  nodeId: string
  nodeName: string
}) {
  const { data: runPayload, error: runError, isLoading: runLoading } = useSWR(
    runId ? ["canvas-node-run", runId] : null,
    () => runsApi.getWithSteps(runId),
    { revalidateOnFocus: false },
  )
  const { data: outcomePayload, error: outcomeError, isLoading: outcomeLoading } = useSWR(
    runId ? ["canvas-node-outcome", runId] : null,
    () => businessOutcomesApi.get(runId),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const step = (runPayload?.steps ?? []).find((raw) => {
    const record = raw as Record<string, unknown>
    const id = String(record.nodeId ?? record.node_id ?? record.stepId ?? record.step_id ?? "")
    const name = String(record.name ?? record.step_name ?? "")
    return id === nodeId || name === nodeName
  }) as Record<string, unknown> | undefined

  const stepStatus = step ? String(step.status ?? "unknown") : null
  const stepError =
    (step?.errorMessage as string | undefined) ??
    (step?.error_message as string | undefined) ??
    (step?.error as string | undefined) ??
    null
  const stepOutput = step?.output as Record<string, unknown> | undefined

  const businessOutcome = (outcomePayload?.businessOutcome ?? null) as BusinessOutcomeDto | null

  if (runLoading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-24 w-full rounded-lg" />
      </div>
    )
  }

  if (runError) {
    return (
      <WorkSectionErrorCard
        title="Could not load run debug"
        message="Refresh or open the full run report."
      />
    )
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-secondary/30 p-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Run debug
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Step status for <span className="font-medium text-foreground">{nodeName}</span>
          {stepStatus ? ` · ${stepStatus}` : " · no matching step yet"}
        </p>
        {stepError ? (
          <p className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1.5 text-xs text-destructive">
            {stepError}
          </p>
        ) : null}
      </div>

      {stepOutput && Object.keys(stepOutput).length > 0 ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Step output
          </p>
          <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-muted/40 p-2 text-[10px]">
            {JSON.stringify(stepOutput, null, 2)}
          </pre>
        </div>
      ) : null}

      {outcomeLoading ? (
        <Skeleton className="h-32 w-full rounded-lg" />
      ) : businessOutcome && !outcomeError ? (
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Business outcome (run-level)
          </p>
          <BusinessOutcomeView outcome={businessOutcome} density="timeline" />
        </div>
      ) : null}
    </div>
  )
}
