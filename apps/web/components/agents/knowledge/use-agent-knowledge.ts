"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { agentKnowledgeApi, sourcesApi, type AgentKnowledgeAssignment } from "@/lib/api"
import type { SourceSyncHistoryItem } from "@/types/api"
import type { SourceIngestionSnapshot } from "./source-ingestion-indicator"
import {
  buildOrgSourceAssignmentPayload,
  buildPackAssignmentPayload,
  formatKnowledgeAssignError,
  formatKnowledgeRemoveError,
  type PackAssignInput,
} from "@/lib/agent-knowledge-assign"

export type AgentKnowledgeTab = "sources" | "expert-packs" | "instructions" | "retrieval"

export function useAgentKnowledge(agentId: string, agentName: string, agentDepartment?: string | null) {
  const [assigningKey, setAssigningKey] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)

  const {
    data: assignmentData,
    isLoading: assignmentsLoading,
    mutate: mutateAssignments,
  } = useSWR(agentId ? `agent/${agentId}/knowledge-assignments` : null, () =>
    agentKnowledgeApi.listAssignments(agentId),
  )

  const { data: capabilities, isLoading: capabilitiesLoading } = useSWR(
    agentId ? `agent/${agentId}/capabilities` : null,
    () => agentKnowledgeApi.getCapabilities(agentId),
  )

  const assignments = assignmentData?.assignments ?? []

  const { data: orgSourcesData, isLoading: orgSourcesLoading, mutate: mutateOrgSources } = useSWR(
    "org-rag-sources",
    () => sourcesApi.list(),
  )

  const orgSources = orgSourcesData?.sources ?? []

  const syncingSourceIds = useMemo(
    () =>
      orgSources
        .filter((source) => {
          const status = String(source.status ?? "").toLowerCase()
          return status === "syncing" || status === "processing"
        })
        .map((source) => String(source.id ?? ""))
        .filter(Boolean),
    [orgSources],
  )

  useSWR(syncingSourceIds.length > 0 ? "org-rag-sources-sync-poll" : null, () => sourcesApi.list(), {
    refreshInterval: 5000,
    onSuccess: () => {
      void mutateOrgSources()
    },
  })

  const [syncHistoryById, setSyncHistoryById] = useState<Map<string, SourceSyncHistoryItem[]>>(new Map())

  useEffect(() => {
    if (syncingSourceIds.length === 0) {
      setSyncHistoryById(new Map())
      return
    }

    let cancelled = false

    async function pollSyncHistory() {
      const entries = await Promise.all(
        syncingSourceIds.map(async (sourceId) => {
          try {
            const { history } = await sourcesApi.getSyncHistory(sourceId)
            return [sourceId, history] as const
          } catch {
            return [sourceId, []] as const
          }
        }),
      )
      if (cancelled) return
      setSyncHistoryById(new Map(entries as Array<[string, SourceSyncHistoryItem[]]>))
      await mutateOrgSources()
    }

    void pollSyncHistory()
    const timer = window.setInterval(() => void pollSyncHistory(), 5000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [mutateOrgSources, syncingSourceIds.join("|")])

  const sourceIngestionById = useMemo(() => {
    const map = new Map<string, SourceIngestionSnapshot>()
    for (const source of orgSources) {
      const id = String(source.id ?? "")
      if (!id) continue
      const history = syncHistoryById.get(id) ?? []
      const latest = history[0]
      const status = String(source.status ?? "").toLowerCase()
      const historyRunning = String(latest?.status ?? "").toLowerCase() === "running"
      const indexing = status === "syncing" || status === "processing" || historyRunning
      const records = typeof latest?.records === "number" ? latest.records : null
      map.set(id, {
        status: indexing ? "syncing" : String(source.status ?? ""),
        documentCount: Number(source.document_count ?? 0) || undefined,
        lastSyncAt: source.last_sync_at ?? source.updated_at ?? latest?.createdAt ?? null,
        syncProgress:
          indexing && records != null && records > 0 ? Math.min(95, Math.round(records / 10)) : null,
      })
    }
    return map
  }, [orgSources, syncHistoryById])

  const assignedPackIds = useMemo(
    () =>
      new Set(
        assignments
          .filter((a) => a.sourceType === "knowledge_pack")
          .map((a) => a.sourceId),
      ),
    [assignments],
  )

  const assignedSourceIds = useMemo(
    () =>
      new Set(
        assignments
          .filter((a) => a.sourceType === "rag_source")
          .map((a) => a.sourceId),
      ),
    [assignments],
  )

  const lastSyncedAt = useMemo(() => {
    const times = assignments
      .map((a) => a.lastSyncedAt)
      .filter(Boolean)
      .map((t) => new Date(String(t)).getTime())
      .filter((n) => !Number.isNaN(n))
    if (times.length === 0) return null
    return new Date(Math.max(...times)).toISOString()
  }, [assignments])

  const summary = useMemo(
    () => ({
      sourceCount: assignments.filter((a) => a.enabled !== false).length,
      indexedLabel:
        capabilities?.connectedKnowledgeSources?.length != null
          ? String(capabilities.connectedKnowledgeSources.length)
          : "Not enough data",
      healthLabel: capabilities?.freshnessStatus ?? "Not enough data",
      lastSyncLabel: lastSyncedAt
        ? new Date(lastSyncedAt).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          })
        : "—",
    }),
    [assignments, capabilities, lastSyncedAt],
  )

  const assignPack = useCallback(
    async (pack: PackAssignInput) => {
      const key = `pack:${pack.id}`
      if (assignedPackIds.has(pack.id)) {
        toast.info(`${pack.name} is already assigned`)
        return true
      }
      setAssigningKey(key)
      try {
        await agentKnowledgeApi.createAssignment(agentId, buildPackAssignmentPayload(pack))
        toast.success(`${pack.name} assigned to ${agentName}`)
        await mutateAssignments()
        return true
      } catch (error) {
        console.error("[agent-knowledge] assign pack failed:", error)
        toast.error(formatKnowledgeAssignError(error, pack.name))
        return false
      } finally {
        setAssigningKey(null)
      }
    },
    [agentId, agentName, assignedPackIds, mutateAssignments],
  )

  const assignOrgSource = useCallback(
    async (source: { id: string; name: string }) => {
      const key = `source:${source.id}`
      if (assignedSourceIds.has(source.id)) {
        toast.info(`${source.name} is already assigned`)
        return true
      }
      setAssigningKey(key)
      try {
        await agentKnowledgeApi.createAssignment(agentId, buildOrgSourceAssignmentPayload(source))
        toast.success(`${source.name} assigned to ${agentName}`)
        await mutateAssignments()
        return true
      } catch (error) {
        console.error("[agent-knowledge] assign source failed:", error)
        toast.error(formatKnowledgeAssignError(error, source.name))
        return false
      } finally {
        setAssigningKey(null)
      }
    },
    [agentId, agentName, assignedSourceIds, mutateAssignments],
  )

  const removeAssignment = useCallback(
    async (assignment: AgentKnowledgeAssignment) => {
      if (!assignment.id || assignment.fromConfig) {
        toast.error("Legacy config-only sources must be re-assigned through the new flow.")
        return false
      }
      setRemovingId(assignment.id)
      try {
        await agentKnowledgeApi.deleteAssignment(agentId, assignment.id)
        toast.success(`${assignment.label} removed from this agent`)
        await mutateAssignments()
        return true
      } catch (error) {
        console.error("[agent-knowledge] remove failed:", error)
        toast.error(formatKnowledgeRemoveError(error, assignment.label))
        return false
      } finally {
        setRemovingId(null)
      }
    },
    [agentId, mutateAssignments],
  )

  return {
    assignments,
    orgSources,
    capabilities,
    summary,
    assignedPackIds,
    assignedSourceIds,
    assigningKey,
    removingId,
    loading: assignmentsLoading || capabilitiesLoading,
    orgSourcesLoading,
    agentDepartment,
    assignPack,
    assignOrgSource,
    removeAssignment,
    mutateAssignments,
    sourceIngestionById,
  }
}

export type AgentKnowledgeState = ReturnType<typeof useAgentKnowledge>
