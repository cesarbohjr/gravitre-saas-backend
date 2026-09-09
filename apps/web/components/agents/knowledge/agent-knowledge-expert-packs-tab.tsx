"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { packAvailabilityLabel } from "@/lib/agent-knowledge-assign"
import { ExpertPackCard } from "./agent-knowledge-card"
import type { AgentKnowledgeState } from "./use-agent-knowledge"

type PackRow = {
  pack_id: string
  label: string
  department: string
  pack_type?: string
  ingestible?: boolean
  hold?: boolean
  recommended?: boolean
  recommended_for_department?: string | null
}

export function AgentKnowledgeExpertPacksTab({
  workspace,
  agentCapabilities,
}: {
  workspace: AgentKnowledgeState
  agentCapabilities?: string[]
}) {
  const dept = (workspace.agentDepartment || "").trim()
  const qs = dept ? `?department=${encodeURIComponent(dept)}` : ""
  const { data, isLoading } = useSWR<{ packs: PackRow[] }>(
    `/api/knowledge-fabric/packs${qs}`,
    fetcher,
    { revalidateOnFocus: false },
  )

  const packs = (data?.packs ?? []).filter((p) => p.pack_type !== "tool_expertise")
  const recommended = packs.filter((p) => p.recommended)
  const other = packs.filter((p) => !p.recommended)

  const reason =
    agentCapabilities && agentCapabilities.length > 0
      ? `Recommended because this agent performs ${agentCapabilities.slice(0, 2).join(", ")}.`
      : dept
        ? `Recommended for ${dept} workflows.`
        : "Recommended for this agent's department."

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading expert packs…</p>
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-[color:var(--g-text-muted)]">
        Platform-curated Gravitre intelligence. Assigning a pack links this agent to shared expert content — it is
        never copied into your private company storage.
      </p>
      {recommended.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">Recommended</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {recommended.map((pack) => {
              const avail = packAvailabilityLabel(pack)
              return (
                <ExpertPackCard
                  key={pack.pack_id}
                  pack={{ ...pack, customerStatus: avail.customerLabel }}
                  assigned={workspace.assignedPackIds.has(pack.pack_id)}
                  recommended
                  recommendationReason={reason}
                  disabled={!avail.assignable}
                  busy={workspace.assigningKey === `pack:${pack.pack_id}`}
                  onAssign={() =>
                    void workspace.assignPack({
                      id: pack.pack_id,
                      name: pack.label,
                      department: pack.department,
                    })
                  }
                />
              )
            })}
          </div>
        </section>
      ) : null}
      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          {recommended.length > 0 ? "All expert packs" : "Expert packs"}
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {(recommended.length > 0 ? other : packs).map((pack) => {
            const avail = packAvailabilityLabel(pack)
            return (
              <ExpertPackCard
                key={pack.pack_id}
                pack={{ ...pack, customerStatus: avail.customerLabel }}
                assigned={workspace.assignedPackIds.has(pack.pack_id)}
                disabled={!avail.assignable}
                busy={workspace.assigningKey === `pack:${pack.pack_id}`}
                onAssign={() =>
                  void workspace.assignPack({
                    id: pack.pack_id,
                    name: pack.label,
                    department: pack.department,
                  })
                }
              />
            )
          })}
        </div>
      </section>
    </div>
  )
}
