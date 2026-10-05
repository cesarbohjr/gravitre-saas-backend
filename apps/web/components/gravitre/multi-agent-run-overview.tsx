"use client"

import Link from "next/link"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { SwarmConvergenceDiagram } from "@/components/agent-swarm/swarm-convergence-diagram"

export function MultiAgentRunOverview({
  activeRuns,
  completedRuns,
  totalRuns,
}: {
  activeRuns: number | null
  completedRuns: number | null
  totalRuns: number | null
}) {
  return (
    <section className="grid items-center gap-5 border-b border-border pb-6 sm:grid-cols-[minmax(0,1fr)_14rem]">
      <div className="space-y-2">
        <p className={TYPE.eyebrow}>Coordinate / Execution</p>
        <h2 className={TYPE.sectionTitle}>
          Divide the work. Inspect the evidence.
        </h2>
        <p className={cn(TYPE.bodyMuted, "max-w-2xl")}>
          Follow each agent’s subtask and the council’s recommendation. A
          completed recommendation does not establish that external actions were
          verified. Configure your roster in{" "}
          <Link
            href={APP_ROUTES.agents}
            className="underline underline-offset-4"
          >
            AI Team
          </Link>
          .
        </p>
        <p className={TYPE.meta}>
          Recent {totalRuns ?? "Not reported"} runs ·{" "}
          {activeRuns ?? "Not reported"} active ·{" "}
          {completedRuns ?? "Not reported"} completed
        </p>
      </div>
      <div>
        <SwarmConvergenceDiagram variant="panel" />
        <p className={cn(TYPE.meta, "mt-2 text-center")}>
          Coordination model · illustrative
        </p>
      </div>
    </section>
  )
}
