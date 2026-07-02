"use client"

import { SimulationCard } from "@/components/intelligence/simulation-card"

export function ApprovalSimulationPreview({
  simulation,
}: {
  simulation: Record<string, unknown> | null | undefined
}) {
  if (!simulation || Object.keys(simulation).length === 0) return null
  return (
    <div className="mb-3 rounded-xl border border-border bg-card/50 p-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Simulation preview</p>
      <SimulationCard simulation={simulation} />
    </div>
  )
}
