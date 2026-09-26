"use client"

/**
 * Command OS work canvas — presents canonical executionResult artifacts.
 * Does not invent UI-only artifact state or replace the transcript.
 */

import { NucleoRun } from "@/components/icons/nucleo/semantic"
import { TYPE, NUCLEO_SIZE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  CanonicalArtifactTable,
  canonicalArtifactRows,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { PreviewCodePane } from "@/components/gravitre/assistant/preview-code-pane"

export function GravitreAIWorkCanvas({
  executionResult,
  pendingTask,
}: {
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
}) {
  const primary = executionResult?.artifacts?.[0]
  const kind =
    String(executionResult?.structured?.kind || primary?.kind || "").trim() || null
  const title =
    executionResult?.title ||
    executionResult?.task_label ||
    primary?.title ||
    pendingTask?.params?.goal ||
    pendingTask?.params?.label ||
    "Work"
  const body =
    executionResult?.structured?.completionCard?.whatHappened ||
    executionResult?.structured?.whatThisMeans ||
    executionResult?.body ||
    (pendingTask ? "Awaiting confirmation." : null)
  const ok = executionResult?.success
  const rows = executionResult ? canonicalArtifactRows(executionResult) : []
  const planId = executionResult?.structured?.plan_id || executionResult?.entity_id
  const observationIds =
    executionResult?.structured?.observation_ids || primary?.metadata?.observation_ids
  const exportable =
    executionResult?.structured?.exportable ?? primary?.metadata?.exportable
  const markdown =
    executionResult?.structured?.code ||
    executionResult?.structured?.content ||
    primary?.metadata?.code ||
    null

  return (
    <section
      data-gravitre-work-canvas=""
      className="flex h-full min-h-0 flex-col overflow-y-auto border-l border-divide p-4"
    >
      <p className={TYPE.eyebrow}>{pendingTask ? "EXECUTE" : "Artifact"}</p>
      <h2 className={cn(TYPE.sectionTitle, "mt-2")}>{title}</h2>
      {kind ? (
        <p className={cn(TYPE.meta, "mt-1")} data-testid="canonical-artifact-kind">
          {kind}
        </p>
      ) : null}
      {ok === true ? (
        <p className={cn(TYPE.meta, "mt-1 text-[color:var(--g-brand)]")}>Completed</p>
      ) : ok === false ? (
        <p className={cn(TYPE.meta, "mt-1 text-[color:var(--g-danger)]")}>Did not complete</p>
      ) : pendingTask ? (
        <p className={cn(TYPE.meta, "mt-1 inline-flex items-center gap-1")}>
          <NucleoRun width={NUCLEO_SIZE.row} height={NUCLEO_SIZE.row} />
          In progress
        </p>
      ) : null}
      {body ? <p className={cn(TYPE.body, "mt-3")}>{body}</p> : null}
      <CanonicalArtifactTable
        rows={rows}
        planId={planId}
        observationIds={observationIds}
        exportable={exportable}
      />
      {!rows.length && markdown ? (
        <div className="mt-3">
          <PreviewCodePane
            title={title}
            code={String(markdown)}
            previewFormat={executionResult?.structured?.previewFormat || "markdown"}
          />
        </div>
      ) : null}
    </section>
  )
}
