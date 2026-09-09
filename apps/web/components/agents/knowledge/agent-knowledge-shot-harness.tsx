"use client"

import { useMemo, useState } from "react"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { cn } from "@/lib/utils"
import type { AgentKnowledgeAssignment } from "@/lib/api"
import { packAvailabilityLabel } from "@/lib/agent-knowledge-assign"
import { ExpertPackCard } from "./agent-knowledge-card"
import { AgentKnowledgeSourcesTab } from "./agent-knowledge-sources-tab"
import type { AgentKnowledgeState } from "./use-agent-knowledge"

const SHOT_AGENT_ID = "agt_lead_triage"
const SHOT_AGENT_NAME = "Inbound Lead Triage"

const SHOT_PACKS = [
  {
    pack_id: "pack.sales-playbook",
    label: "RevOps Playbook",
    department: "Sales",
    recommended: true,
    ingestible: true,
    hold: false,
  },
  {
    pack_id: "pack.support-macros",
    label: "Support Macros",
    department: "Support",
    recommended: false,
    ingestible: true,
    hold: false,
  },
]

const SHOT_SOURCES = [
  {
    id: "src_northwind_kb",
    name: "Northwind product FAQ",
    description: "Indexed answers from the public help center.",
    type: "url",
    status: "active",
    document_count: 128,
    last_sync_at: "2026-09-08T16:00:00.000Z",
  },
  {
    id: "src_pricing_docs",
    name: "Pricing enablement deck",
    description: "PDF uploads from revenue ops.",
    type: "file",
    status: "syncing",
    document_count: 42,
    last_sync_at: null,
  },
]

/**
 * Interactive harness for Playwright — assign/remove without a live backend.
 * Fixture-only; unreachable in production (shots layout 404).
 */
export function AgentKnowledgeShotHarness() {
  const [activeTab, setActiveTab] = useState<"sources" | "expert-packs">("expert-packs")
  const [assignments, setAssignments] = useState<AgentKnowledgeAssignment[]>([
    {
      id: "asn_fixture_pack",
      sourceType: "knowledge_pack",
      sourceId: "pack.sales-playbook",
      label: "RevOps Playbook",
      enabled: true,
      freshnessStatus: "fresh",
    },
  ])
  const [assigningKey, setAssigningKey] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const assignedPackIds = useMemo(
    () => new Set(assignments.filter((a) => a.sourceType === "knowledge_pack").map((a) => a.sourceId)),
    [assignments],
  )
  const assignedSourceIds = useMemo(
    () => new Set(assignments.filter((a) => a.sourceType === "rag_source").map((a) => a.sourceId)),
    [assignments],
  )

  const sourceIngestionById = useMemo(() => {
    const map = new Map<string, { status?: string; documentCount?: number; lastSyncAt?: string | null; syncProgress?: number | null }>()
    for (const source of SHOT_SOURCES) {
      map.set(source.id, {
        status: source.status,
        documentCount: source.document_count,
        lastSyncAt: source.last_sync_at,
        syncProgress: source.status === "syncing" ? 62 : null,
      })
    }
    return map
  }, [])

  const workspace = {
    assignments,
    orgSources: SHOT_SOURCES,
    capabilities: {
      connectedKnowledgeSources: assignments.map((a) => a.label),
      freshnessStatus: "fresh",
    },
    summary: {
      sourceCount: assignments.length,
      indexedLabel: String(assignments.length),
      healthLabel: "fresh",
      lastSyncLabel: "Sep 8, 4:00 PM",
    },
    assignedPackIds,
    assignedSourceIds,
    assigningKey,
    removingId,
    loading: false,
    orgSourcesLoading: false,
    agentDepartment: "Sales",
    assignPack: async (pack: { id: string; name: string; department: string }) => {
      setAssigningKey(`pack:${pack.id}`)
      await new Promise((r) => setTimeout(r, 120))
      setAssignments((prev) => [
        ...prev.filter((a) => !(a.sourceType === "knowledge_pack" && a.sourceId === pack.id)),
        {
          id: `asn_${pack.id}`,
          sourceType: "knowledge_pack",
          sourceId: pack.id,
          label: pack.name,
          enabled: true,
          freshnessStatus: "fresh",
        },
      ])
      setAssigningKey(null)
      return true
    },
    assignOrgSource: async (source: { id: string; name: string }) => {
      setAssigningKey(`source:${source.id}`)
      await new Promise((r) => setTimeout(r, 120))
      setAssignments((prev) => [
        ...prev.filter((a) => !(a.sourceType === "rag_source" && a.sourceId === source.id)),
        {
          id: `asn_${source.id}`,
          sourceType: "rag_source",
          sourceId: source.id,
          label: source.name,
          enabled: true,
          freshnessStatus: "fresh",
        },
      ])
      setAssigningKey(null)
      return true
    },
    removeAssignment: async (assignment: AgentKnowledgeAssignment) => {
      if (!assignment.id) return false
      setRemovingId(assignment.id)
      await new Promise((r) => setTimeout(r, 120))
      setAssignments((prev) => prev.filter((a) => a.id !== assignment.id))
      setRemovingId(null)
      return true
    },
    mutateAssignments: async () => {},
    sourceIngestionById,
  } satisfies AgentKnowledgeState

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6" data-testid="agent-knowledge-shot">
      <GravitrePageHeader
        eyebrow="Agent knowledge"
        title={SHOT_AGENT_NAME}
        description="Assign expert packs and organization knowledge without copying content into private storage."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <GravitreMetric label="Sources" value={String(workspace.summary.sourceCount)} />
        <GravitreMetric label="Indexed" value={workspace.summary.indexedLabel} />
        <GravitreMetric label="Freshness" value={workspace.summary.healthLabel} />
        <GravitreMetric label="Last sync" value={workspace.summary.lastSyncLabel} />
      </div>

      <div className="flex flex-wrap gap-2 border-b border-border pb-2">
        {(
          [
            { id: "sources", label: "Sources" },
            { id: "expert-packs", label: "Expert Packs" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-[color:var(--g-brand)]/10 text-[color:var(--g-brand)]"
                : "text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "sources" ? (
        <AgentKnowledgeSourcesTab workspace={workspace} agentId={SHOT_AGENT_ID} agentName={SHOT_AGENT_NAME} />
      ) : (
        <ShotExpertPacks workspace={workspace} />
      )}
    </div>
  )
}

function ShotExpertPacks({ workspace }: { workspace: AgentKnowledgeState }) {
  const recommended = SHOT_PACKS.filter((p) => p.recommended)
  const other = SHOT_PACKS.filter((p) => !p.recommended)
  const reason = "Recommended because this agent performs company enrichment, duplicate detection."

  return (
    <div className="space-y-6">
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
                onAssign={() => void workspace.assignPack({ id: pack.pack_id, name: pack.label, department: pack.department })}
              />
            )
          })}
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">All expert packs</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {other.map((pack) => {
            const avail = packAvailabilityLabel(pack)
            return (
              <ExpertPackCard
                key={pack.pack_id}
                pack={{ ...pack, customerStatus: avail.customerLabel }}
                assigned={workspace.assignedPackIds.has(pack.pack_id)}
                disabled={!avail.assignable}
                busy={workspace.assigningKey === `pack:${pack.pack_id}`}
                onAssign={() => void workspace.assignPack({ id: pack.pack_id, name: pack.label, department: pack.department })}
              />
            )
          })}
        </div>
      </section>
    </div>
  )
}
