"use client"

/**
 * Every real number on Knowledge › Memory, from the memory-promotion admin API
 * (/api/admin/memory-promotion/*) and the agent list (/api/agents).
 */
import { useMemo } from "react"
import useSWR from "swr"
import { agentsApi, memoryPromotionApi, type PromotionCandidate } from "@/lib/api"
import { readNumber } from "@/lib/intelligence/helpers"
import {
  PENDING_STATUS,
  autoPromotionToMemoryItem,
  candidateToMemoryItem,
  type MemoryItem,
} from "./memory-model"

/** Look back far enough that "Auto" lists more than the last day. */
const AUTO_WINDOW = "720h"

export const ORG_MEMORY_SWR_KEYS = {
  all: "intelligence/memory/candidates/all",
  pending: "intelligence/memory/candidates/pending",
  rejected: "intelligence/memory/candidates/rejected",
  written: "intelligence/memory/candidates/written",
  auto: "intelligence/memory/auto",
  audit: "intelligence/memory/audit",
  agents: "intelligence/memory/agents",
} as const

export type MemoryPolicy = {
  minOccurrences: number | null
  minDepartments: number | null
}

export function useOrgMemory(enabled: boolean) {
  const all = useSWR(enabled ? ORG_MEMORY_SWR_KEYS.all : null, () => memoryPromotionApi.candidates({ limit: 200 }), {
    revalidateOnFocus: false,
  })
  const pending = useSWR(enabled ? ORG_MEMORY_SWR_KEYS.pending : null, () =>
    memoryPromotionApi.candidates({ status: PENDING_STATUS, limit: 100 }),
  )
  const rejected = useSWR(
    enabled ? ORG_MEMORY_SWR_KEYS.rejected : null,
    () => memoryPromotionApi.candidates({ status: "rejected", limit: 50 }),
    { revalidateOnFocus: false },
  )
  const written = useSWR(
    enabled ? ORG_MEMORY_SWR_KEYS.written : null,
    () => memoryPromotionApi.candidates({ status: "written", limit: 1 }),
    { revalidateOnFocus: false },
  )
  const auto = useSWR(enabled ? ORG_MEMORY_SWR_KEYS.auto : null, () =>
    memoryPromotionApi.recentAutoPromotions({ since: AUTO_WINDOW, limit: 50 }),
  )
  const audit = useSWR(enabled ? ORG_MEMORY_SWR_KEYS.audit : null, () => memoryPromotionApi.audit({ limit: 50 }))
  const agents = useSWR(enabled ? ORG_MEMORY_SWR_KEYS.agents : null, () => agentsApi.list(), {
    revalidateOnFocus: false,
  })

  const agentList = useMemo(() => agents.data?.agents ?? [], [agents.data])
  const agentNames = useMemo(
    () => Object.fromEntries(agentList.map((agent) => [String(agent.id), agent.name])),
    [agentList],
  )
  const candidatesById = useMemo(() => {
    const map: Record<string, PromotionCandidate> = {}
    for (const row of all.data?.items ?? []) map[row.id] = row
    return map
  }, [all.data])

  const queues = useMemo<Record<"pending" | "auto" | "rejected", MemoryItem[]>>(
    () => ({
      pending: (pending.data?.items ?? []).map((c) => candidateToMemoryItem(c, "pending", agentNames)),
      auto: (auto.data?.items ?? []).map((r, i) => autoPromotionToMemoryItem(r, i, candidatesById, agentNames)),
      rejected: (rejected.data?.items ?? []).map((c) => candidateToMemoryItem(c, "rejected", agentNames)),
    }),
    [pending.data, auto.data, rejected.data, agentNames, candidatesById],
  )

  const auditItems = useMemo(
    () => ((audit.data?.items as Array<Record<string, unknown>> | undefined) ?? []),
    [audit.data],
  )

  /** Funnel counts. null = not loaded yet (renders "—"). */
  const pipeline = useMemo(() => {
    const allItems = all.data?.items ?? []
    return {
      observed: all.data ? readNumber(all.data.total, allItems.length) : null,
      repeating: all.data ? allItems.filter((c) => readNumber(c.frequency, 0) >= 2).length : null,
      needsReview: pending.data ? readNumber(pending.data.total, pending.data.items.length) : null,
      orgMemory: written.data ? readNumber(written.data.total, written.data.items.length) : null,
      repeatingIsPartial: Boolean(all.data && readNumber(all.data.total, 0) > allItems.length),
    }
  }, [all.data, pending.data, written.data])

  /** Thresholds the backend reports with each candidate, or in the audit snapshot. */
  const policy = useMemo<MemoryPolicy>(() => {
    const tc = [...(pending.data?.items ?? []), ...(all.data?.items ?? [])].find((c) => c.thresholdComparison)
      ?.thresholdComparison
    if (tc) {
      return {
        minOccurrences: readNumber(tc.autoPromoteMinOccurrences, null),
        minDepartments: readNumber(tc.autoPromoteMinDepartments, null),
      }
    }
    for (const row of auditItems) {
      const snap = (row.thresholdSnapshot ?? row.threshold_snapshot) as Record<string, unknown> | undefined
      if (snap && (snap.min_occurrences != null || snap.min_departments != null)) {
        return {
          minOccurrences: readNumber(snap.min_occurrences, null),
          minDepartments: readNumber(snap.min_departments, null),
        }
      }
    }
    return { minOccurrences: null, minDepartments: null }
  }, [pending.data, all.data, auditItems])

  const watchedAgents = useMemo(() => agentList.filter((a) => a.status !== "error"), [agentList])
  const runningAgents = useMemo(() => agentList.filter((a) => a.status === "processing"), [agentList])

  async function refresh() {
    await Promise.all([all.mutate(), pending.mutate(), rejected.mutate(), written.mutate(), auto.mutate(), audit.mutate()])
  }

  return {
    error: pending.error ?? all.error ?? null,
    isLoading: !pending.data && !pending.error,
    agentsLoaded: Boolean(agents.data),
    queues,
    auditItems,
    auditLoading: !audit.data && !audit.error,
    auditError: audit.error ?? null,
    pipeline,
    policy,
    agents: agentList,
    watchedAgents,
    runningAgents,
    hasRealCandidates: queues.pending.length + queues.auto.length + queues.rejected.length > 0,
    refresh,
  }
}
