"use client"

import { useMemo } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { connectorVendorKey } from "@/lib/connectors"
import { workflowUsesVendor } from "@/components/connectors/connector-linkage"
import { readinessOf } from "@/components/plays/plays-board-model"
import type { PlayListItem } from "@/lib/api"
import type { Workflow, WorkflowListResponse } from "@/types/api"

/**
 * What uses each connector, from the real catalogs: Plays (GET /api/plays,
 * readiness.connector_groups) and workflows (GET /api/workflows, definitions
 * that reference the vendor). Agents come from useAgentsByVendor.
 */

export type PlayRef = { key: string; name: string; waiting: boolean; ready: boolean }

type GroupLike = { status?: string; vendors?: unknown }

function groupsOf(item: PlayListItem): GroupLike[] {
  const groups = (item.readiness as { connector_groups?: unknown }).connector_groups
  return Array.isArray(groups) ? (groups.filter((g) => g && typeof g === "object") as GroupLike[]) : []
}

function vendorsOf(group: GroupLike): string[] {
  return Array.isArray(group.vendors) ? group.vendors.map((v) => connectorVendorKey(String(v))) : []
}

export function usePlays(enabled: boolean) {
  const { data } = useSWR<{ plays?: PlayListItem[] }>(enabled ? "/api/plays" : null, apiFetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  })
  return useMemo(() => {
    const plays = data?.plays ?? []
    const byVendor = new Map<string, PlayRef[]>()
    /** Plays held back only by a connector, keyed by the vendors that would unlock them. */
    const waitingOn = new Map<string, Set<string>>()
    let waiting = 0
    for (const item of plays) {
      const state = readinessOf(item)
      const ref: PlayRef = { key: item.play.key, name: item.play.name, waiting: state === "connector", ready: state === "ready" }
      if (ref.waiting) waiting += 1
      for (const group of groupsOf(item)) {
        for (const vendor of vendorsOf(group)) {
          const list = byVendor.get(vendor) ?? []
          if (!list.some((p) => p.key === ref.key)) list.push(ref)
          byVendor.set(vendor, list)
          if (ref.waiting && group.status !== "AVAILABLE") {
            const set = waitingOn.get(vendor) ?? new Set<string>()
            set.add(ref.key)
            waitingOn.set(vendor, set)
          }
        }
      }
    }
    return { loaded: Boolean(data), plays, byVendor, waiting, waitingOn }
  }, [data])
}

export function useWorkflows(enabled: boolean) {
  const { data } = useSWR<WorkflowListResponse>(enabled ? "/api/workflows" : null, apiFetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  })
  return useMemo(() => {
    const workflows: Workflow[] = data?.workflows ?? []
    const cache = new Map<string, Workflow[]>()
    const forVendor = (vendor: string): Workflow[] => {
      const key = connectorVendorKey(vendor)
      if (!key) return []
      const hit = cache.get(key)
      if (hit) return hit
      const found = workflows.filter((w) => workflowUsesVendor(w, key))
      cache.set(key, found)
      return found
    }
    return { loaded: Boolean(data), workflows, forVendor }
  }, [data])
}

/** "2 agents and 1 workflow", skipping zeros; "" when nothing uses it. */
export function usageSentence(agents: number, workflows: number, plays = 0): string {
  const parts: string[] = []
  if (agents) parts.push(`${agents} ${agents === 1 ? "agent" : "agents"}`)
  if (workflows) parts.push(`${workflows} ${workflows === 1 ? "workflow" : "workflows"}`)
  if (plays) parts.push(`${plays} ${plays === 1 ? "play" : "plays"}`)
  if (parts.length <= 1) return parts[0] ?? ""
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`
}

/** "2 min ago", "3 h ago", "Jun 4" from an ISO time; "Never" when missing. */
export function relativeTime(value: string | null | undefined, now = Date.now()): string {
  if (!value) return "Never"
  const t = new Date(value).getTime()
  if (Number.isNaN(t)) return String(value)
  const s = Math.max(0, Math.round((now - t) / 1000))
  if (s < 60) return "Just now"
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86_400) return `${Math.floor(s / 3600)} h ago`
  if (s < 7 * 86_400) return `${Math.floor(s / 86_400)} d ago`
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/** Sync interval choices the backend scheduler honours (it reads hours, days and weeks). */
export const SYNC_INTERVALS: Array<{ value: string; label: string }> = [
  { value: "1h", label: "Every hour" },
  { value: "6h", label: "Every 6 hours" },
  { value: "12h", label: "Every 12 hours" },
  { value: "24h", label: "Every day" },
  { value: "1w", label: "Every week" },
]

export function syncIntervalLabel(value: string | null | undefined): string {
  const raw = String(value ?? "").trim().toLowerCase()
  if (!raw) return "Every hour"
  const hit = SYNC_INTERVALS.find((opt) => opt.value === raw)
  if (hit) return hit.label
  if (raw === "daily" || raw === "day") return "Every day"
  if (raw === "weekly" || raw === "week") return "Every week"
  return raw
}
