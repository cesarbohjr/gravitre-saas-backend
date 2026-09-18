"use client"

/**
 * Command OS work canvas — shown beside conversation when a real artifact
 * or execution exists. Does not replace the transcript.
 */

import { NucleoRun } from "@/components/icons/nucleo/semantic"
import { TYPE, NUCLEO_SIZE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"

export function GravitreAIWorkCanvas({
  executionResult,
  pendingTask,
}: {
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
}) {
  const title =
    executionResult?.title ||
    executionResult?.task_label ||
    pendingTask?.params?.goal ||
    pendingTask?.params?.label ||
    "Work"
  const body =
    executionResult?.structured?.completionCard?.whatHappened ||
    executionResult?.structured?.whatThisMeans ||
    executionResult?.body ||
    (pendingTask ? "Awaiting confirmation." : null)
  const ok = executionResult?.success

  return (
    <section
      data-gravitre-work-canvas=""
      className="flex h-full min-h-0 flex-col overflow-y-auto border-l border-divide p-4"
    >
      <p className={TYPE.eyebrow}>{pendingTask ? "EXECUTE" : "Artifact"}</p>
      <h2 className={cn(TYPE.sectionTitle, "mt-2")}>{title}</h2>
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
    </section>
  )
}
