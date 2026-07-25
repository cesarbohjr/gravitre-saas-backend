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
          {(() => {
            const reasoning =
              (stepOutput.reasoning_summary as string | undefined) ||
              (stepOutput.reasoningSummary as string | undefined) ||
              ((stepOutput.ai_reasoning as Record<string, unknown> | undefined)
                ?.reasoning_summary as string | undefined)
            const confidence =
              typeof stepOutput.confidence === "number"
                ? stepOutput.confidence
                : typeof (stepOutput.ai_reasoning as Record<string, unknown> | undefined)?.confidence ===
                    "number"
                  ? ((stepOutput.ai_reasoning as Record<string, unknown>).confidence as number)
                  : null
            const isEstimate =
              stepOutput.confidence_is_estimate ??
              stepOutput.confidenceIsEstimate ??
              (stepOutput.ai_reasoning as Record<string, unknown> | undefined)?.confidence_is_estimate ??
              (stepOutput.ai_reasoning as Record<string, unknown> | undefined)?.confidenceIsEstimate
            const source =
              (stepOutput.confidence_source as string | undefined) ||
              (stepOutput.confidenceSource as string | undefined) ||
              ((stepOutput.ai_reasoning as Record<string, unknown> | undefined)
                ?.confidence_source as string | undefined) ||
              ((stepOutput.ai_reasoning as Record<string, unknown> | undefined)
                ?.confidenceSource as string | undefined)
            if (!reasoning && confidence == null) return null
            return (
              <div className="mt-2 rounded-md border border-violet-500/25 bg-violet-500/5 px-2 py-1.5">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-violet-400">
                  Branch reasoning (Module C)
                </p>
                {reasoning ? (
                  <p className="mt-1 text-xs text-foreground">{reasoning}</p>
                ) : null}
                {confidence != null ? (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {isEstimate !== false ? "Estimated confidence" : "Confidence"}{" "}
                    {Math.round(confidence * 100)}%
                    {source ? ` · ${source}` : ""}
                  </p>
                ) : null}
              </div>
            )
          })()}
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
