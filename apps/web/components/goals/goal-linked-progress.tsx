"use client"

import useSWR from "swr"
import { accountIntelligenceApi, isFeatureOff } from "@/lib/api"

function summary(byStatus: Record<string, number>): string {
  return Object.entries(byStatus)
    .map(([status, n]) => `${n} ${status.replaceAll("_", " ")}`)
    .join(", ")
}

/** Progress counted from work and jobs linked to this goal. Renders nothing while switched off. */
export function GoalLinkedProgress({ goalId }: { goalId: string }) {
  const { data, error } = useSWR(["goal-linked-progress", goalId], () => accountIntelligenceApi.goalLinkedProgress(goalId), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  if (isFeatureOff(error) || (!data && !error)) return null
  if (error || !data) return <p className="text-sm text-muted-foreground">Linked work couldn&apos;t load.</p>
  if (!data.linkedWork || !data.linkedJobs) return null
  const total = data.linkedWork.total + data.linkedJobs.total
  return (
    <section aria-labelledby="goal-linked-heading" className="space-y-1">
      <h2 id="goal-linked-heading" className="font-sans text-xl font-medium">Linked work</h2>
      {total === 0 ? (
        <p className="text-sm text-muted-foreground">No work or agent jobs are linked to this goal yet.</p>
      ) : (
        <>
          <p className="text-sm text-foreground">
            {data.completionPercentage == null
              ? "Nothing countable is linked yet."
              : `${data.completionPercentage}% of linked work is done.`}
          </p>
          {data.linkedWork.total ? (
            <p className="text-xs text-muted-foreground">Work: {summary(data.linkedWork.byStatus)}</p>
          ) : null}
          {data.linkedJobs.total ? (
            <p className="text-xs text-muted-foreground">Agent jobs: {summary(data.linkedJobs.byStatus)}</p>
          ) : null}
        </>
      )}
    </section>
  )
}
