"use client"

import { SimulationCard } from "@/components/intelligence/simulation-card"

export function ApprovalSimulationPreview({
  simulation,
}: {
  simulation: Record<string, unknown> | null | undefined
}) {
  if (!simulation || Object.keys(simulation).length === 0) return null
  return (
    <div className="mb-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/40">
      <p className="mb-2 text-xs font-medium text-zinc-600 dark:text-zinc-300">Simulation preview</p>
      <SimulationCard simulation={simulation} />
    </div>
  )
}
